# Hello World Conductor Sample

**Time to build:** 5 minutes  
**Level:** Beginner  
**What you'll learn:** Basic Conductor concepts

---

## Quick Start

### 1. Run

```bash
python main.py
# 👋 Hello, World!

python main.py --name Alice
# 👋 Hello, Alice!

python main.py --plan
# (Show plan without executing)
```

### 2. View Logs

```bash
cat logs/hello-world.log
# HELLO-20260604-001234 | 👋 Hello, World! | 2026-06-04T00:12:34
```

---

## What This Teaches

✅ **conductor.json** — Project manifest  
✅ **Agents** — Simple agent that takes input, returns output  
✅ **Context** — Pass metadata to agents  
✅ **Async/await** — Conductor uses async patterns  
✅ **Logging** — Persist results for audit trail  

---

## File Structure

```
hello-world/
├── conductor.json     # Manifest (project metadata)
├── main.py           # Entry point (orchestrator)
├── agents/
│   └── greeter.py    # Agent implementation
├── logs/             # Output directory (created by main.py)
└── README.md         # This file
```

---

## Conductor Concepts

### 1. **conductor.json** (Manifest)

```json
{
  "name": "hello-world",
  "version": "1.0.0",
  "agents": [
    {
      "name": "greeter",
      "capabilities": ["greet"]
    }
  ]
}
```

**Purpose:** Declare your project, agents, and integrations.

---

### 2. **Agent** (greeter.py)

```python
async def greeter_agent(context: dict, name: str = "World", **kwargs):
    """Agent function."""
    return {
        "greeting": f"Hello, {name}!",
        "timestamp": datetime.utcnow().isoformat(),
    }
```

**Key Points:**
- Async function (supports concurrent execution)
- Takes `context` dict (metadata about the run)
- Takes `**kwargs` for parameters
- Returns dict (structured output)

---

### 3. **Context** (Execution Metadata)

```python
context = {
    "run_id": "HELLO-20260604-001234",
    "user": "developer",
    "mode": "execute",
}
```

**Passed to:** All agents, used for logging/audit trail.

---

### 4. **Main Loop** (main.py)

```python
# 1. Load manifest
manifest = json.load("conductor.json")

# 2. Create context
context = {"run_id": "...", "user": "..."}

# 3. Call agent
result = await greeter_agent(context=context, name="Alice")

# 4. Log result
log_path.write(f"{context['run_id']} | {result}\n")
```

**Pattern:** Parse → Validate → Execute → Log

---

## Next Steps

### 🔧 Modify This Sample

1. **Add a new agent:**
   ```python
   # agents/farewell.py
   async def farewell_agent(context: dict, name: str = "Friend", **kwargs):
       return {"farewell": f"Goodbye, {name}!"}
   ```

2. **Call it from main():**
   ```python
   from agents.farewell import farewell_agent
   result2 = await farewell_agent(context=context, name=args.name)
   ```

3. **Run:**
   ```bash
   python main.py --name Alice
   ```

### 📚 Learn More

- [QUICKSTART.md](../../docs/QUICKSTART.md) — 10-minute overview
- [samples/security-remediation/](../security-remediation/) — Production pipeline
- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — Deep dive

### 🚀 Build a Real App

Copy this structure for your own project:

```bash
cp -r hello-world my-project
cd my-project
# 1. Edit conductor.json
# 2. Write agents/ that call real LLMs
# 3. Add logging/metrics
# 4. Deploy to production
```

---

## Files Explained

### conductor.json

```json
{
  "name": "hello-world",           // Project identifier
  "version": "1.0.0",              // Semantic version
  "agents": [                      // Declare agents
    {
      "name": "greeter",           // Agent name
      "description": "...",        // What it does
      "capabilities": ["greet"]    // What it can do
    }
  ],
  "settings": {
    "mode": "plan",                // "plan" or "execute"
    "log_level": "INFO",           // Verbosity
    "llm_provider": "stub",        // "stub", "openai", "copilot"
    "human_gate": false            // Require human approval
  }
}
```

### agents/greeter.py

```python
async def greeter_agent(context: dict, name: str = "World", **kwargs):
    """
    Args:
        context: Conductor metadata {run_id, user, mode, ...}
        name: Name to greet (keyword arg)
        **kwargs: Additional parameters
    
    Returns:
        dict with greeting, timestamp, etc.
    """
```

### main.py

```python
# 1. Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--name", default="World")
parser.add_argument("--plan", action="store_true")

# 2. Load manifest
with open("conductor.json") as f:
    manifest = json.load(f)

# 3. Create context
context = {
    "run_id": "HELLO-...",
    "user": "developer",
    "mode": "plan" if args.plan else "execute",
}

# 4. Show plan (always)
print(f"📋 Plan: {plan_description}")

# 5. Halt if plan-only mode
if args.plan:
    return

# 6. Execute agent
result = await greeter_agent(context=context, **vars(args))

# 7. Log result
log_file.write(...)
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| ModuleNotFoundError | Run from hello-world/ directory, not parent |
| No output | Check logs/hello-world.log |
| Agent crashes | Add try/except in main.py |
| Want to see prompts? | Use real LLM (replace "stub") and increase log_level |

---

## Key Takeaways

✅ Conductor is async-first (agents are coroutines)  
✅ Context flows through all agents (audit trail)  
✅ Manifests (conductor.json) declare structure  
✅ Agents are pure functions (input → output)  
✅ Logs persist decisions (who decided what, when)  
✅ Easy to extend (copy structure, add agents)  

---

## See Also

- [ADR-009: conductor.json Manifest](../../docs/adr/ADR-009.md)
- [ADR-010: CLI Commands](../../docs/adr/ADR-010.md)
- [API Reference](../../docs/API_REFERENCE.md)
