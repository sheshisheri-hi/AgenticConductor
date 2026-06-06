# A2A Server Guide: Expose Agents as HTTP Endpoints

**Sprint 10 (ADR-011 Tier 3):** Secure agent-to-agent communication via HTTP/mTLS

---

## Overview

The **A2A Server** exposes Conductor agents as HTTP endpoints so external frameworks (Claude, LangChain, CrewAI) can call them as peers.

**Key Features:**
- ✅ HTTP/REST API for agent calls
- ✅ mTLS certificate verification (mutual authentication)
- ✅ Built-in health checks and statistics
- ✅ Call tracking and latency monitoring
- ✅ Multiple agents per server

---

## Quick Start

### 1. Create an Agent

```python
# my_agents.py
async def my_agent(context: dict, query: str = "", **kwargs):
    """Sample agent that analyzes code."""
    return {
        "agent": "code_analyzer",
        "query": query,
        "analysis": "TODO analysis",
        "confidence": 0.95,
    }
```

### 2. Expose as A2A Server

```python
# main.py
import asyncio
from fastapi import FastAPI
from conductor_core.a2a.server.agent_server import AgentServer
from conductor_core.a2a.server.http_transport import create_a2a_app
from my_agents import my_agent

async def main():
    # Create agent server
    server = AgentServer(
        agent_id="code_analyzer",
        agent_name="CodeAnalyzer",
        agent_callable=my_agent,
        capabilities=["analyze", "review"],
        version="1.0.0",
    )
    
    # Create FastAPI app with A2A transport
    app, transport = create_a2a_app()
    transport.register_agent(server)
    
    # Start server
    await transport.start_server(host="0.0.0.0", port=8000)

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Call from External Framework

```python
import requests

# Health check
resp = requests.get("http://localhost:8000/health")
print(resp.json())  # {'status': 'healthy', 'agents': 1}

# Get agent info
resp = requests.get("http://localhost:8000/a2a/info?agent_id=code_analyzer")
print(resp.json())
# {
#   'agent_id': 'code_analyzer',
#   'agent_name': 'CodeAnalyzer',
#   'capabilities': ['analyze', 'review'],
#   'status': 'running'
# }

# Call agent
resp = requests.post("http://localhost:8000/a2a/call", json={
    "agent_id": "code_analyzer",
    "context": {
        "repo": "my-repo",
        "file": "app.py",
    },
    "params": {
        "query": "Find security issues",
    }
})
print(resp.json())
# {
#   'status': 'success',
#   'agent_id': 'code_analyzer',
#   'result': {
#     'agent': 'code_analyzer',
#     'query': 'Find security issues',
#     'analysis': 'TODO analysis',
#     'confidence': 0.95,
#   },
#   'timestamp': '2026-06-04T00:00:00'
# }
```

---

## API Reference

### Endpoints

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-06-04T00:00:00",
  "agents": 1
}
```

---

#### `GET /a2a/info`

Get agent metadata.

**Query Parameters:**
- `agent_id` (required): Agent identifier

**Response:**
```json
{
  "agent_id": "code_analyzer",
  "agent_name": "CodeAnalyzer",
  "capabilities": ["analyze", "review"],
  "version": "1.0.0",
  "created_at": "2026-06-04T00:00:00",
  "status": "running"
}
```

**Errors:**
- `404 Not Found` — Agent not registered

---

#### `POST /a2a/call`

Call an agent via A2A protocol.

**Request Body:**
```json
{
  "agent_id": "code_analyzer",
  "context": {
    "repo": "my-repo",
    "file": "app.py",
    "user": "alice@company.com"
  },
  "params": {
    "query": "Find security issues",
    "max_results": 10
  }
}
```

**Response (Success):**
```json
{
  "status": "success",
  "agent_id": "code_analyzer",
  "result": {
    "agent": "code_analyzer",
    "query": "Find security issues",
    "analysis": "Found 3 SQL injection risks",
    "confidence": 0.95
  },
  "timestamp": "2026-06-04T00:00:00"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "agent_id": "code_analyzer",
  "error": "Agent crashed: KeyError on 'query'",
  "timestamp": "2026-06-04T00:00:00"
}
```

**Errors:**
- `400 Bad Request` — Missing `agent_id` or invalid JSON
- `404 Not Found` — Agent not registered
- `500 Internal Server Error` — Agent raised exception

---

#### `GET /a2a/agents`

List all registered agents.

**Response:**
```json
{
  "agents": [
    {
      "agent_id": "code_analyzer",
      "agent_name": "CodeAnalyzer",
      "capabilities": ["analyze", "review"],
      "status": "running"
    },
    {
      "agent_id": "security_scanner",
      "agent_name": "SecurityScanner",
      "capabilities": ["scan"],
      "status": "running"
    }
  ],
  "count": 2
}
```

---

#### `GET /a2a/stats/{agent_id}`

Get agent call statistics.

**Path Parameters:**
- `agent_id` (required): Agent identifier

**Response:**
```json
{
  "agent_id": "code_analyzer",
  "total_calls": 42,
  "successful_calls": 40,
  "failed_calls": 2,
  "avg_latency_ms": 234.5,
  "last_call_at": "2026-06-04T00:30:00"
}
```

**Errors:**
- `404 Not Found` — Agent not registered

---

## Securing with mTLS

### 1. Generate Certificates

```python
from pathlib import Path
from conductor_core.security.mtls import CertificateManager

manager = CertificateManager(cert_dir=Path(".conductor/certs"))

# Generate CA (one-time)
manager.generate_ca_certificate()

# Generate agent certificate
cert_path, key_path = manager.generate_agent_certificate(
    agent_id="code_analyzer",
    common_name="code-analyzer.conductor.local",
)

print(f"Certificate: {cert_path}")
print(f"Key: {key_path}")
```

### 2. Start Server with mTLS

```python
from pathlib import Path

app, transport = create_a2a_app(
    mtls_cert_path=Path(".conductor/certs/code_analyzer-cert.pem"),
    mtls_key_path=Path(".conductor/certs/code_analyzer-key.pem"),
)

await transport.start_server(host="0.0.0.0", port=8443)
```

### 3. Call with Client Certificate

```python
import requests

# Provide client certificate for mTLS
resp = requests.post(
    "https://localhost:8443/a2a/call",
    json={
        "agent_id": "code_analyzer",
        "context": {},
        "params": {"query": "test"},
    },
    cert=(
        ".conductor/certs/client-cert.pem",
        ".conductor/certs/client-key.pem",
    ),
    verify=".conductor/certs/ca-cert.pem",  # Verify server certificate
)
```

---

## Multiple Agents

```python
async def main():
    app, transport = create_a2a_app()
    
    # Register multiple agents
    for agent_func in [code_analyzer, security_scanner, performance_profiler]:
        server = AgentServer(
            agent_id=agent_func.__name__,
            agent_name=agent_func.__name__.title(),
            agent_callable=agent_func,
            capabilities=get_capabilities(agent_func),
        )
        transport.register_agent(server)
    
    # Start server
    await transport.start_server()
```

### Call different agents:

```python
# Call code analyzer
requests.post("http://localhost:8000/a2a/call", json={
    "agent_id": "code_analyzer",
    "context": {},
    "params": {},
})

# Call security scanner
requests.post("http://localhost:8000/a2a/call", json={
    "agent_id": "security_scanner",
    "context": {},
    "params": {},
})
```

---

## Error Handling

```python
import requests
from requests.exceptions import RequestException

try:
    resp = requests.post("http://localhost:8000/a2a/call", json={
        "agent_id": "unknown_agent",
        "context": {},
        "params": {},
    }, timeout=30)
    
    if resp.status_code == 404:
        print(f"Agent not found: {resp.json()['detail']}")
    elif resp.status_code == 500:
        print(f"Agent error: {resp.json()['error']}")
    else:
        result = resp.json()["result"]
        
except RequestException as e:
    print(f"Network error: {e}")
```

---

## Performance Considerations

| Consideration | Recommendation |
|---|---|
| **Call latency** | Target < 1s for agent execution |
| **Timeout** | Use 30-60s for LLM calls |
| **Concurrent calls** | Use connection pooling, manage thread pool |
| **Error recovery** | Implement exponential backoff retry |
| **Logging** | Enable structured logging for debugging |

---

## Testing

```bash
# Run integration tests
pytest conductor_core/tests/integration/test_a2a_http_transport.py -v

# Test with mock agent
python main.py --test

# Load test
ab -n 1000 -c 10 http://localhost:8000/health
```

---

## Examples

### Example 1: Code Analyzer Agent

```python
async def code_analyzer(context: dict, file_path: str = "", **kwargs):
    """Analyze code file for issues."""
    with open(file_path) as f:
        code = f.read()
    
    # TODO: Call LLM to analyze
    return {
        "file": file_path,
        "issues": [],
        "confidence": 0.85,
    }
```

### Example 2: Security Scanner Agent

```python
async def security_scanner(context: dict, query: str = "", **kwargs):
    """Scan for security issues."""
    # TODO: Call Snyk/SonarQube integration
    return {
        "query": query,
        "findings": [],
        "severity": "low",
    }
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **Agent not found (404)** | Ensure agent is registered before calling |
| **Connection refused** | Check server is running and listening on correct port |
| **Timeout** | Increase timeout, check agent performance |
| **mTLS certificate error** | Verify certificate paths and permissions |
| **Agent crashes** | Check agent logs, add error handling |

---

## See Also

- [Threat Model](./THREAT_MODEL.md) — A2A security threat analysis
- [Deployment Guide](./DEPLOYMENT_GUIDE.md) — Production deployment checklist
- [ADR-011](./adr/ADR-011.md) — A2A Protocol specification

