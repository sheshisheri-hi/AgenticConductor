# API Reference

**Version:** 1.0.0 | **Last Updated:** 2024-06-04

## Table of Contents
1. [WorkflowOrchestrator](#workfloworchestrator)
2. [WorkflowContext](#workflowcontext)
3. [WorkflowGraph](#workflowgraph)
4. [AgentServer](#agentserver)
5. [@validated_agent Decorator](#validated_agent-decorator)
6. [TokenScrubber](#tokenscrubber)
7. [DependencyVerifier](#dependencyverifier)
8. [Result Stores](#result-stores)
9. [Error Codes](#error-codes)

## WorkflowOrchestrator

Main orchestration engine for building and executing workflows.

**File:** `conductor_core/orchestrator.py`

### Constructor

```python
from conductor_core.orchestrator import WorkflowOrchestrator

orchestrator = WorkflowOrchestrator(
    mode: str = "execute",          # "execute" or "plan"
    timeout: int = 300,              # seconds per agent
    max_retries: int = 3,           # retry count on failure
)
```

### Key Methods

#### build()
Builds a DAG from agent definitions.

```python
graph = orchestrator.build(
    agents: List[Agent] | Dict[str, Callable],
    edges: List[Tuple[str, str]],  # (from_agent, to_agent)
)
```

**Returns:** `WorkflowGraph`

**Raises:**
- `ValueError` if agents not unique
- `ValidationError` if cycles detected

**Example:**
```python
from conductor_core.orchestrator import WorkflowOrchestrator

orchestrator = WorkflowOrchestrator()
graph = orchestrator.build(
    agents={
        "triage": triage_agent,
        "analyze": analyze_agent,
        "remediate": remediate_agent,
    },
    edges=[
        ("triage", "analyze"),
        ("analyze", "remediate"),
    ]
)
```

#### execute()
Executes a workflow against a context.

```python
result = await orchestrator.execute(
    graph: WorkflowGraph,
    context: WorkflowContext,
    validate_output: bool = True,  # run output validation
)
```

**Returns:** `WorkflowContext` (modified with results)

**Raises:**
- `TimeoutError` if agent exceeds timeout
- `ValidationError` if output validation fails
- `ExecutionError` on agent failure

**Example:**
```python
from conductor_core.context import WorkflowContext

context = WorkflowContext(
    run_id="demo-1",
    user="developer",
    mode="execute",
)

result = await orchestrator.execute(graph, context)
print(f"Decisions: {result.decisions}")
print(f"Total cost: ${result.telemetry.total_cost}")
```

#### validate()
Validates a graph without executing.

```python
errors = orchestrator.validate(graph: WorkflowGraph)
```

**Returns:** `List[str]` (empty if valid)

## WorkflowContext

Execution context carrying data between agents.

**File:** `conductor_core/context.py`

### Constructor

```python
from conductor_core.context import WorkflowContext

context = WorkflowContext(
    run_id: str,              # unique run identifier
    user: str,                # user making the request
    mode: str = "execute",    # "execute" or "plan"
    payload: Dict = None,     # extra data
)
```

### Key Methods

#### get_agent_output()
Retrieves output from a previous agent in the workflow.

```python
output = context.get_agent_output(agent_name: str)
# or access via dict
output = context.payload.get(agent_name)
```

**Returns:** `Any` (whatever the agent returned)

**Example:**
```python
@validated_agent(schema=RemediationPlan)
async def remediate_agent(context, **kwargs):
    # Get findings from previous agent
    findings = context.get_agent_output("analyze_agent")
    # Process findings...
    return plan
```

#### set_mode()
Changes execution mode mid-workflow.

```python
context.set_mode("plan")  # show plan without executing
```

## WorkflowGraph

DAG representation of workflow.

**File:** `conductor_core/graph.py`

### Constructor

```python
from conductor_core.graph import WorkflowGraph

graph = WorkflowGraph(
    agents: Dict[str, Callable],
    edges: List[Tuple[str, str]],
)
```

### Key Properties

- `nodes: Dict[str, Agent]` — Agent definitions
- `edges: List[Tuple[str, str]]` — Dependencies
- `is_dag: bool` — True if acyclic
- `execution_order: List[str]` — Topologically sorted agents

## AgentServer

Wraps agents for HTTP exposure via A2A.

**File:** `conductor_core/a2a/server/agent_server.py`

### Constructor

```python
from conductor_core.a2a.server import AgentServer

server = AgentServer(
    agent_id: str,
    agent_callable: Callable,
    description: str = "",
    timeout_seconds: int = 30,
)
```

### Key Methods

#### call()
Executes agent with given context and kwargs.

```python
result = await server.call(context: Dict, **kwargs)
```

**Returns:** `Dict` with execution result

**Example:**
```python
from conductor_core.a2a.server import AgentServer

async def my_agent(context, **kwargs):
    return {"status": "ok", "result": "..."}

server = AgentServer("my-agent", my_agent)
result = await server.call({"run_id": "demo"}, data="...")
```

## @validated_agent Decorator

Validates agent output against Pydantic schema.

**File:** `conductor_core/decorators/validated_agent.py`

### Usage

```python
from conductor_core.decorators.validated_agent import validated_agent
from pydantic import BaseModel

class OutputSchema(BaseModel):
    status: str
    result: str

@validated_agent(schema=OutputSchema)
async def my_agent(context, **kwargs):
    return {"status": "ok", "result": "done"}
```

### Parameters

- `schema: BaseModel` — Pydantic schema to validate against
- `raise_on_invalid: bool = False` — Raise exception if validation fails (default: log warning)
- `strict_mode: bool = False` — Raise on extra fields (default: allow extras)

### Error Handling

```python
@validated_agent(schema=OutputSchema, raise_on_invalid=True)
async def strict_agent(context, **kwargs):
    # If output doesn't match schema, raises ValidationError
    return invalid_output

# With error handling
try:
    result = await strict_agent(context)
except ValidationError as e:
    print(f"Output validation failed: {e}")
```

## TokenScrubber

Prevents secrets from appearing in logs.

**File:** `conductor_core/secrets/token_scrubber.py`

### Setup

```python
from conductor_core.secrets.token_scrubber import ScrubFilter
import logging

# Add filter to root logger
filter = ScrubFilter()
logging.getLogger().addFilter(filter)

# Now all logs are automatically scrubbed
import logging
log = logging.getLogger(__name__)
log.info("GitHub token: gh_abc123def456...")  # ✅ Outputs: "GitHub token: <REDACTED>"
```

### Supported Patterns

- GitHub tokens: `gh_*` (personal access)
- AWS Access Keys: `AKIA*`
- AWS Secret Keys: `aws_secret_access_key`
- JWT tokens: `eyJ*`
- API keys: `api_key`, `apikey`, `api-key`
- Database passwords: `password=*`
- Snyk tokens: `snyk_*`
- And 5+ more patterns

### Custom Patterns

```python
from conductor_core.secrets.token_scrubber import ScrubFilter

filter = ScrubFilter()
filter.add_pattern(r"my_secret_\w+")  # Custom regex
logging.getLogger().addFilter(filter)
```

## DependencyVerifier

Verifies dependencies for supply chain risks.

**File:** `conductor_core/supply_chain/dependencies.py`

### Usage

```python
from conductor_core.supply_chain.dependencies import DependencyVerifier

verifier = DependencyVerifier()
result = await verifier.verify("requirements.txt")

if result["has_risks"]:
    print(f"⚠️  Risks found: {result['risks']}")
else:
    print("✅ All dependencies verified")
```

### Returns

```python
{
    "has_risks": bool,
    "risks": [
        {
            "package": "vulnerable-pkg",
            "version": "1.0.0",
            "risk": "Known CVE-2024-12345",
            "severity": "HIGH",
        }
    ],
    "verified_at": "2024-06-04T...",
}
```

## Result Stores

Persist workflow results.

### SQLiteResultStore

**File:** `conductor_core/stores/sqlite_store.py`

```python
from conductor_core.stores.sqlite_store import SQLiteResultStore

store = SQLiteResultStore("runs.db")

# Save result
await store.save(result: WorkflowContext)

# Retrieve result
result = await store.get(run_id: str)

# Query results
results = await store.find(
    filter_dict={"user": "alice", "scenario": "snyk"},
    limit=10
)
```

### PostgresResultStore

**File:** `conductor_core/stores/postgres_store.py`

```python
from conductor_core.stores.postgres_store import PostgresResultStore

store = PostgresResultStore("postgresql+asyncpg://user:pass@host/db")

# Same interface as SQLite
await store.save(result)
result = await store.get(run_id)
```

## Error Codes

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ValidationError` | Agent output doesn't match schema | Check @validated_agent schema definition |
| `TimeoutError` | Agent exceeded timeout | Increase timeout or optimize agent |
| `ExecutionError` | Agent raised exception | Check agent implementation and logs |
| `CycleError` | Workflow graph has cycles | Ensure DAG (no circular dependencies) |
| `ImportError` | Missing dependency | Install missing package |

### Examples

```python
from conductor_core.exceptions import (
    ValidationError,
    TimeoutError,
    ExecutionError,
    CycleError,
)

try:
    result = await orchestrator.execute(graph, context)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
except TimeoutError as e:
    logger.error(f"Agent timed out: {e}")
except ExecutionError as e:
    logger.error(f"Execution failed: {e}")
except CycleError as e:
    logger.error(f"Workflow has cycles: {e}")
```

---

## Quick Reference

| Component | Import | Purpose |
|-----------|--------|---------|
| `WorkflowOrchestrator` | `conductor_core.orchestrator` | Main orchestration |
| `WorkflowContext` | `conductor_core.context` | Execution context |
| `WorkflowGraph` | `conductor_core.graph` | DAG representation |
| `@validated_agent` | `conductor_core.decorators` | Output validation |
| `AgentServer` | `conductor_core.a2a.server` | HTTP agent wrapper |
| `TokenScrubber` | `conductor_core.secrets` | Log scrubbing |
| `DependencyVerifier` | `conductor_core.supply_chain` | Dependency check |
| `SQLiteResultStore` | `conductor_core.stores` | Result persistence |

## See Also

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and data flows
- [SECURITY_HARDENING.md](SECURITY_HARDENING.md) — Production deployment
- [samples/security-remediation/](../samples/projects/security-remediation/) — Full example
