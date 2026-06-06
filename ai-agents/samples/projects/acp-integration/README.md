# ACP Integration Conductor Sample

**Time to build:** ~10 hours  
**Level:** Intermediate  
**Purpose:** Demonstrate Azure Copilot style intent → context → response orchestration, plus optional A2A server mode.

---

## What It Shows

This sample models a lightweight Azure Copilot integration:

1. `intent_classifier` labels the incoming request.
2. `context_builder` assembles the right supporting context.
3. `response_generator` emits a deterministic response.
4. `a2a_server.py` exposes the same agents as HTTP-callable A2A endpoints.

The sample is designed so that `python main.py` works even without optional HTTP dependencies installed.

---

## Run Locally

```bash
cd acp-integration

python main.py
python main.py --intent --message "How do I remediate a Snyk finding?"
python main.py --build-context --message "Explain the workflow sample"
python main.py --generate-response --message "How do I expose this as HTTP?"
python main.py --plan
python main.py --help
```

---

## Run as an HTTP Server for ACP

```bash
python main.py --a2a-server
```

If `fastapi` and `uvicorn` are installed, the sample starts an HTTP server on port `8002`. Otherwise it prints a preview of the routes, registered agents, and a simulated client response.

Expected HTTP routes:

- `GET /health`
- `GET /a2a/agents`
- `GET /a2a/info?agent_id=intent_classifier`
- `POST /a2a/call`

Example client call:

```bash
curl -X POST http://localhost:8002/a2a/call       -H 'content-type: application/json'       -d '{"agent_id":"response_generator","params":{"message":"Need deployment help"}}'
```

---

## Performance Characteristics

- all agents are async and safe to compose in larger workflows
- the default path is deterministic and avoids network calls
- HTTP mode reuses the same agent implementations as CLI mode
- the sample is ideal for demos, contract testing, and endpoint shape reviews

---

## Security Considerations

For production Azure Copilot integrations, add:

- mTLS certificates between the client and A2A server
- authentication and authorization at the ingress layer
- request validation and rate limiting
- scrubbed logs to avoid leaking bearer tokens
- isolated model credentials for each environment

`conductor_core.a2a.server.http_transport` already anticipates an mTLS-based deployment shape, so this sample provides a compact reference for that path.

---

## How to Extend It

- plug in a real intent classifier or Azure-specific prompt layer
- enrich context from a knowledge base or ticket system
- route responses into Teams, GitHub, or an ACP action endpoint
- add telemetry, tracing, and replay support like `consumer-showcase`
- secure the HTTP layer and publish it behind an API gateway
