# Security Hardening Guide

**Version:** 1.0.0 | **Last Updated:** 2024-06-04

Production deployment checklist for Conductor Framework with 5-layer security stack.

## 1. Pre-Deployment Checklist

### Environment Variables
- [ ] LLM API keys in environment variables (never in code)
  ```bash
  export OPENAI_API_KEY="sk-..."
  export ANTHROPIC_API_KEY="..."
  export GITHUB_TOKEN="gh_..."  # Will be scrubbed by TokenScrubber
  ```

- [ ] Database connection strings secure
  ```bash
  export CONDUCTOR_DB_URL="postgresql+asyncpg://user:pass@host/db"
  ```

- [ ] Snyk/GitHub/ADO tokens NOT in config files
  ```bash
  # ❌ WRONG: config.json has "snyk_token": "snyk_..."
  # ✅ RIGHT: export SNYK_API_TOKEN="snyk_..."
  ```

### File Permissions
- [ ] .conductor/certs/ directory mode 0700 (owner only)
  ```bash
  chmod 700 .conductor/certs
  ```

- [ ] Private key files mode 0600
  ```bash
  chmod 600 .conductor/certs/*.key
  ```

- [ ] Database files mode 0600 (if SQLite)
  ```bash
  chmod 600 runs.db
  ```

### Secrets Scanning
- [ ] Run TokenScrubber before deploying
  ```bash
  python -c "
  from conductor_core.secrets.token_scrubber import ScrubFilter
  f = ScrubFilter()
  # Test patterns
  test_cases = [
      'gh_abc123def456789',
      'AKIAIOSFODNN7EXAMPLE',
      'api_key=secret123',
  ]
  for case in test_cases:
      print(f.scrub_line(case))
  "
  ```

- [ ] Run dependency verification
  ```bash
  python -c "
  from conductor_core.supply_chain.dependencies import DependencyVerifier
  import asyncio
  
  async def check():
      verifier = DependencyVerifier()
      result = await verifier.verify('requirements.txt')
      if result['has_risks']:
          print('⚠️ Risks found:', result['risks'])
          exit(1)
  
  asyncio.run(check())
  "
  ```

## 2. Production Settings

### Logging Configuration
```python
from conductor_core.config.logging_config import configure_logging
from conductor_core.secrets.token_scrubber import ScrubFilter
import logging

# Set up logging with security
configure_logging(
    level="INFO",  # Never DEBUG in production
    log_file="/var/log/conductor/app.log",
    json_format=True,  # Structured logs
)

# Add token scrubber
filter = ScrubFilter()
logging.getLogger().addFilter(filter)

# Rotate logs
from logging.handlers import RotatingFileHandler
handler = RotatingFileHandler(
    "/var/log/conductor/app.log",
    maxBytes=100_000_000,  # 100 MB
    backupCount=10,
)
logging.getLogger().addHandler(handler)
```

### Timeout Settings
```python
from conductor_core.orchestrator import WorkflowOrchestrator

orchestrator = WorkflowOrchestrator(
    mode="execute",
    timeout=60,          # 60 seconds per agent (production)
    max_retries=2,       # Fewer retries to catch errors faster
)
```

### Database Security
- [ ] For SQLite in production: Use encryption
  ```python
  # Consider using encrypted SQLite (sqlcipher)
  from conductor_core.stores.sqlite_store import SQLiteResultStore
  
  # Use env var for path
  db_path = os.environ.get("CONDUCTOR_DB_PATH", "runs.db")
  store = SQLiteResultStore(db_path)
  ```

- [ ] For PostgreSQL: Use SSL
  ```bash
  export CONDUCTOR_DB_URL="postgresql+asyncpg://user:pass@host/db?ssl=require"
  ```

## 3. mTLS Setup for A2A Communication

### Certificate Generation
```bash
# Generate CA certificate (one-time)
python -c "
from conductor_core.security.mtls import CertificateManager
mgr = CertificateManager(cert_dir='.conductor/certs')
mgr.generate_ca_certificate()
print('✅ CA certificate generated')
"

# Generate per-agent certificates
python -c "
from conductor_core.security.mtls import CertificateManager
mgr = CertificateManager(cert_dir='.conductor/certs')

agents = ['triage_agent', 'analyzer', 'remediation_planner']
for agent in agents:
    mgr.generate_agent_certificate(agent_id=agent)
    print(f'✅ Generated cert for {agent}')
"
```

### Certificate Renewal
```bash
# Before expiration, regenerate
python -c "
from conductor_core.security.mtls import CertificateManager
from pathlib import Path

mgr = CertificateManager(cert_dir='.conductor/certs')
mgr.generate_ca_certificate(force=True)  # Regenerate CA
print('✅ CA renewed')

# Regenerate all agent certs
agents = ['triage_agent', 'analyzer', 'remediation_planner']
for agent in agents:
    mgr.generate_agent_certificate(agent_id=agent, force=True)
    print(f'✅ Renewed cert for {agent}')
"
```

### Client Verification
A2A server automatically verifies client certificates:
```python
from conductor_core.a2a.server import create_a2a_app

app, transport = create_a2a_app()

# Clients must present valid certificate
# Invalid certs are rejected with 401 Unauthorized
```

## 4. Supply Chain Security

### Dependency Verification on Startup
```python
from conductor_core.supply_chain.dependencies import DependencyVerifier
import asyncio
import sys

async def verify_on_startup():
    verifier = DependencyVerifier()
    result = await verifier.verify("requirements.txt")
    
    if result["has_risks"]:
        for risk in result["risks"]:
            print(f"❌ {risk['package']}: {risk['risk']}")
        sys.exit(1)  # Prevent deployment
    
    print("✅ All dependencies verified")

# Call on app startup
asyncio.run(verify_on_startup())
```

### Dependency Update Strategy
- [ ] Pin major versions in requirements.txt
  ```
  conductor-core==1.0.*
  pydantic>=2.0,<3.0
  ```

- [ ] Use dependency locking (pip-compile)
  ```bash
  pip-compile requirements.in > requirements.txt
  pip-sync requirements.txt
  ```

- [ ] Regular updates (weekly)
  ```bash
  pip-audit  # Check for known vulnerabilities
  ```

## 5. Secret Management

### LLM API Keys
```bash
# ✅ GOOD: Environment variable
export OPENAI_API_KEY="sk-..."

# ❌ BAD: Hardcoded in config
config = {"api_key": "sk-..."}
```

### Agent Credentials
```python
# ✅ GOOD: Read from env
import os
snyk_token = os.environ.get("SNYK_API_TOKEN")
if not snyk_token:
    raise RuntimeError("SNYK_API_TOKEN not set")

# Pass to agent
result = await snyk_agent(context, token=snyk_token)
# TokenScrubber will redact it from logs
```

### Never Commit Secrets
```bash
# Add to .gitignore
echo ".conductor/certs/" >> .gitignore
echo ".env" >> .gitignore
echo "*.key" >> .gitignore

# Pre-commit hook to prevent accidental commits
# Use tool like detect-secrets
pip install detect-secrets
detect-secrets scan --all-files
```

### Audit Logging
```python
import logging

audit_log = logging.getLogger("conductor.audit")

# Log secret access (without revealing the secret)
def get_snyk_token():
    token = os.environ.get("SNYK_API_TOKEN")
    if token:
        audit_log.info("SNYK_API_TOKEN accessed", extra={"user": "system"})
    return token
```

## 6. Monitoring & Alerting

### What to Monitor
```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
agent_calls = Counter("conductor_agent_calls_total", "Total agent calls", ["agent"])
agent_errors = Counter("conductor_agent_errors_total", "Failed agent calls", ["agent"])
agent_duration = Histogram("conductor_agent_duration_seconds", "Agent execution time")
agents_running = Gauge("conductor_agents_running", "Currently running agents")

# Example usage in orchestrator
try:
    agent_calls.labels(agent=agent_name).inc()
    agents_running.inc()
    
    result = await execute_agent(...)
    
    agent_duration.observe(elapsed_time)
finally:
    agents_running.dec()
```

### Alerts to Configure
- [ ] **Secrets in logs:** TokenScrubber pattern misses
- [ ] **Agent timeouts:** Slow agents or hung processes
- [ ] **Authentication failures:** Invalid mTLS certificates
- [ ] **Supply chain risks:** Vulnerable dependencies detected
- [ ] **Error rate:** >1% agent failure rate
- [ ] **Resource usage:** CPU >80%, Memory >85%

### Integration with Existing Systems
```bash
# Send logs to ELK stack
export CONDUCTOR_LOGGER="elasticsearch://host:9200/conductor"

# Send metrics to Prometheus
export CONDUCTOR_METRICS="prometheus://host:9090"

# Send alerts to PagerDuty
export ALERTING_WEBHOOK="https://events.pagerduty.com/v2/enqueue"
```

## 7. Incident Response

### If Secret Leaked
1. **Immediate:**
   - [ ] Revoke the compromised credential
   - [ ] Alert the team
   
2. **Within 1 hour:**
   - [ ] Rotate all related credentials
   - [ ] Search logs for usage of leaked secret
   - [ ] Check if external access occurred
   
3. **Within 24 hours:**
   - [ ] Review access logs
   - [ ] Determine scope of exposure
   - [ ] Update security policies

### If Agent Compromised
1. **Immediate:**
   - [ ] Disable agent
   - [ ] Stop all workflows using it
   - [ ] Revoke its mTLS certificate
   
2. **Investigation:**
   - [ ] Review agent logs
   - [ ] Trace all data it processed
   - [ ] Check for unauthorized outputs

### Trace Affected Runs
```python
from conductor_core.stores.sqlite_store import SQLiteResultStore

store = SQLiteResultStore("runs.db")

# Find all runs using compromised agent
results = await store.find(
    filter_dict={"agents": "snyk_agent"},
    since="2024-06-01T00:00:00Z"
)

for result in results:
    print(f"Run {result.run_id} used snyk_agent")
    print(f"  User: {result.user}")
    print(f"  Payload: {result.payload}")
```

## 8. Compliance Checklist

### OWASP Top 10 Coverage

| Vulnerability | Conductor Defense | Status |
|---|---|---|
| Injection | Parameterized queries, input validation | ✅ |
| Broken Authentication | mTLS certificates for A2A | ✅ |
| Sensitive Data Exposure | TokenScrubber redacts logs | ✅ |
| XML/XXE | Not applicable (no XML parsing) | ✅ |
| Broken Access Control | Agent isolation, context-based auth | ✅ |
| Security Misconfiguration | Pre-deployment checklist | ✅ |
| XSS | Not applicable (backend only) | ✅ |
| Insecure Deserialization | Pydantic schema validation | ✅ |
| Using Components with Known Vulns | DependencyVerifier scans | ✅ |
| Insufficient Logging | Structured logs + TokenScrubber | ✅ |

### Data Retention Policy
- [ ] Run results: 90 days (configurable)
- [ ] Logs: 30 days (configurable)
- [ ] Certificates: Until expiration + 7 days
- [ ] Audit logs: 1 year (compliance)

### Audit Trail
```python
# Every important action should be logged
audit_log.info("Agent registered", extra={
    "agent_id": "snyk",
    "capabilities": ["triage"],
    "timestamp": datetime.utcnow().isoformat(),
    "user": "admin",
})
```

---

## Production Deployment Script

```bash
#!/bin/bash
set -e

echo "🔐 Conductor Security Hardening"

# 1. Verify dependencies
echo "1. Verifying dependencies..."
python3 -c "
from conductor_core.supply_chain.dependencies import DependencyVerifier
import asyncio, sys

async def check():
    verifier = DependencyVerifier()
    result = await verifier.verify('requirements.txt')
    if result['has_risks']:
        print(f'❌ Risks found: {result[\"risks\"]}')
        sys.exit(1)

asyncio.run(check())
" || exit 1

# 2. Generate mTLS certificates
echo "2. Setting up mTLS..."
python3 -c "
from conductor_core.security.mtls import CertificateManager
mgr = CertificateManager('.conductor/certs')
mgr.generate_ca_certificate()
for agent in ['triage', 'analyzer', 'remediation']:
    mgr.generate_agent_certificate(agent_id=agent)
" || exit 1

# 3. Set file permissions
echo "3. Securing files..."
chmod 700 .conductor/certs
chmod 600 .conductor/certs/*.key

# 4. Verify TokenScrubber
echo "4. Testing TokenScrubber..."
python3 -c "
from conductor_core.secrets.token_scrubber import ScrubFilter
f = ScrubFilter()
print(f.scrub_line('GitHub token: gh_abc123def456789'))
"

echo "✅ Security hardening complete!"
echo "📋 Next steps:"
echo "   1. Set environment variables (OPENAI_API_KEY, SNYK_API_TOKEN, etc.)"
echo "   2. Configure database (CONDUCTOR_DB_URL)"
echo "   3. Start application: python main.py --a2a-server"
echo "   4. Monitor logs for security events"
```

## Troubleshooting

### TokenScrubber not redacting secrets
- Verify filter is added: `logging.getLogger().addFilter(ScrubFilter())`
- Check pattern coverage: `ScrubFilter().patterns` (add custom patterns if needed)

### mTLS certificate errors
- Verify certs exist: `ls -la .conductor/certs/`
- Regenerate if needed: `python -c "...generate_agent_certificate..."`

### High latency with security features
- TokenScrubber: ~2% overhead
- Output validation: ~5% overhead
- mTLS: ~10-20ms per call
- Consider caching if throughput critical

---

**See Also:**
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [THREAT_MODEL.md](THREAT_MODEL.md) — Security analysis
- [samples/security-remediation/](../samples/projects/security-remediation/) — Reference implementation
