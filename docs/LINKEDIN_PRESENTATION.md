# AgenticConductor — LinkedIn presentation

Use this file when you post, present, or send a narrative about the project.  
The developer README is [`../README.md`](../README.md).

---

## Status (say this first)

**AgenticConductor is a proof-of-concept / experimental framework.** It is a personal research repo: a YAML-driven multi-agent kernel plus a security-remediation showcase. It is **not** a product, **not** production-certified, **not** on PyPI, and **not** a competitor that “beats Devin” or “replaces MetaGPT.”

Those systems solve different jobs. The interesting part is the **job Conductor chose**: governed pipelines over inbound work items, with topology in config, confidence as a first-class signal, plan mode that cannot push a PR, and an audit store of every prompt.

If you only remember one sentence:

> I did not try to build another autonomous software engineer. I tried to build the **orchestration kernel** I would want if a security team had to explain every agent decision in an incident review.

---

## The story (2-minute version)

Most agent demos look like this: a chat loop, a pile of tools, and a prayer that the model does the right thing.

Enterprise work looks like this: a CVE lands. Someone has to decide if it is in scope. Someone has to plan a fix. Someone has to review the plan without rubber-stamping the planner. Someone has to **not** push a branch until a human is ready. And six months later, someone has to answer *why* the pipeline proceeded.

That is not “an agent that codes.” That is a **workflow with gates**.

Conductor’s experiment:

1. **Filters before tokens** — drop INFO severity and empty repos in YAML. Zero LLM cost.
2. **Stages in YAML** — triage → analyze → resolve → plan → (optional) code → review → git. Reorder without a Python deploy.
3. **Confidence loop** — if the model is unsure, enrich and retry; if still unsure, escalate. Do not silently proceed.
4. **Plan vs execute** — `stop_before: true` on the code/git stages. Plan mode is a safety property, not a comment in a prompt.
5. **Adversarial review in parallel** — gatekeeper and reviewer fire together. They do **not** see each other’s draft. Merge with `all_must_pass`. No group-chat anchoring.
6. **Replay** — every system prompt, user prompt, and raw completion is stored. `conductor trace` is the postmortem UI.

The reference app is security remediation (Snyk, Sonar, BlackDuck, ADO). The kernel (`conductor-core`) does not know what a CVE is. That split is the point: **domain in agents + YAML; mechanics in the core.**

---

## One diagram

```
                    inbound work item (CVE, SAST, ticket)
                                      │
                                      ▼
                         ┌─────────────────────┐
                         │  Filter (no LLM)    │  reject noise
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │  Router             │  pick a YAML graph
                         └──────────┬──────────┘
                                    ▼
              ┌─────────────────────────────────────────────┐
              │  Orchestrator                               │
              │  sequential stages  │  parallel review gate │
              │  confidence retry   │  plan: stop_before    │
              └──────────────────────────────┬──────────────┘
                                             ▼
                         append-only decisions + prompts
                         SQLite / Postgres + OTEL + CLI
```

---

## How it compares

Comparisons are category errors if you flatten them into “who wins.” Use this table as **positioning**, not a benchmark.

### Devin (Cognition)

| | Devin | Conductor (this PoC) |
|---|---|---|
| Category | **Product**: autonomous software engineer | **Framework**: embeddable workflow kernel |
| Typical ask | “Fix this bug / implement this ticket in the repo” | “Run *this* declared pipeline on *this* work item” |
| Who owns the graph? | Vendor | You (YAML + agent registry) |
| Side-effect control | Product UX / policies | `mode: plan` + `stop_before` in the graph |
| Audit | Vendor-grade product logging | Your store: prompts, confidence, tokens, cost |
| Open source | No | This repo (experiment; license not published) |
| Strength | Open-ended coding, repo navigation, tests, PRs | Governed multi-agent ops with explainability |
| Weakness vs the other | You cannot fork the orchestrator | Will not magically be a senior engineer |

**Fair line for a post:** Devin tries to *be* the engineer. Conductor tries to *be the conductor* — stages, gates, and a score you can audit. Different products. I am not claiming Conductor writes better code than Devin.

### MetaGPT

| | MetaGPT | Conductor (this PoC) |
|---|---|---|
| Metaphor | A **software company in a box** (PM, architect, engineer, QA) | A **production pipeline** (filter → route → gated stages) |
| Typical ask | “Build X from this one-line PRD” | “Triage this finding and either plan a fix or stop” |
| Coordination | SOP / sequential roles, often conversational | YAML transitions + parallel merge strategies |
| Output | Generated project artifacts | `AgentDecision` trail + optional patch/PR |
| Strength | End-to-end software generation research | Ops-shaped control: filters, plan mode, adversarial gates |
| Weakness vs the other | Not designed as a CVE/SAST ticket bus | Not designed to spawn a startup from a sentence |

**Fair line for a post:** MetaGPT asks *what if the company were agents?* Conductor asks *what if the runbook were agents — and the runbook was YAML?* Inspired by that wave of multi-agent work; not a reimplementation of MetaGPT’s SOP assembly line.

### CrewAI and AutoGen

Easy to start: named roles, a crew, a shared thread. Excellent for brainstorming and debate.

Conductor **rejects shared-thread review on purpose** for security gates. If the reviewer reads the gatekeeper’s “looks good,” independence is gone. Parallel `asyncio.gather` + `all_must_pass` is the experimental answer. Debate-style group chat is a *future* runner, not the default (ADR-005).

### LangGraph (and the LangChain ecosystem)

LangGraph is the right tool when you want **ReAct tool loops**, dynamic edges, and ecosystem integrations.

Conductor evaluated it and did not adopt it as the backbone (ADR-008): YAML-first topology, confidence gating, plan/execute, and per-call session isolation would still have been custom nodes — plus a large dependency tree inside `conductor-core`. That is a trade: **less ecosystem, more opinionated kernel.** If your problem is a tool-calling agent, use LangGraph. If your problem is a governed stage machine with an audit store, this PoC is the sketch.

### One-screen matrix

| Job to be done | Reach for |
|---|---|
| Autonomous repo engineer as a service | Devin |
| Simulate a whole software org from a PRD | MetaGPT |
| Fast role-play crews / conversational agents | CrewAI, AutoGen |
| Stateful tool-calling graphs | LangGraph |
| **Declared, auditable, plan-gated pipelines you own** | **Conductor (experiment)** |

---

## What the PoC actually ships

Speak only to what is in the repo:

- Python 3.11+ monorepo: `conductor-core`, `conductor-agents`, `conductor-integrations`, `conductor-cli`, `consumer-showcase`
- Mock mode: **no API keys** — StubLLM + fixture JSON
- Five demo scenarios (Snyk CVE, Sonar SQLi, BlackDuck license, ADO defect, ADO story)
- CLI: `conductor runs` / `plan` / `trace` (including `--prompts --raw`)
- Optional Copilot LLM, optional real git/PRs in `integration` / `live` modes
- Experimental hardening: schema validation on agent I/O, log secret scrubbing, optional A2A HTTP + mTLS

Do **not** claim in a post:

- Production SLAs, SOC2, or “enterprise ready”
- That token-budget / rate-limit work in ADR-013 is complete
- That this replaces Devin, Copilot Workspace, Cursor, or MetaGPT
- Published PyPI packages or a supported release train

Checkpoint markdown in the repo is sprint diary. It is optimistic. Prefer this document and the root README for public wording.

---

## Slide / carousel outline (8 cards)

Copy into a carousel or a talk. One idea per card.

**1 — Title**  
AgenticConductor  
A YAML-driven kernel for governed multi-agent workflows  
*Proof of concept — not a product*

**2 — The mismatch**  
Chat-loop agents ≠ security runbooks  
We need filters, gates, plan mode, and an audit trail

**3 — The bet**  
Topology in YAML  
Confidence as a stop signal  
Reviewers who cannot see each other

**4 — Runtime**  
Filter → route → stages → parallel merge → persist  
`stop_before` = plan mode cannot push git

**5 — vs Devin**  
Devin = the engineer (product)  
Conductor = the conductor (framework you own)  
Different jobs

**6 — vs MetaGPT**  
MetaGPT = company simulation from a PRD  
Conductor = ticket bus with a declared graph  
Inspired, not cloned

**7 — vs LangGraph / Crews**  
LangGraph: ReAct and dynamic graphs  
Crews: shared-thread debate  
Conductor: light kernel, YAML, isolated parallel review

**8 — Ask**  
Clone and run `make demo-snyk` with no tokens  
Read the ADRs  
Fork the kernel — do not wait for a vendor to invent your runbook  
*Experimental. No production claims.*

---

## Ready-to-post LinkedIn copy

### Short post (~1,300 characters — paste-friendly)

```
I have been experimenting with a multi-agent kernel I call AgenticConductor.

This is a proof of concept, not a product. It will not replace Devin. It will not replace MetaGPT. Those tools are solving different problems, and they are further along in their categories than this repo is in mine.

Devin is an autonomous software engineer — a product that is the teammate. MetaGPT is a fascinating “software company in a box”: PM, architect, engineer, QA assembling a project from a PRD.

I wanted something closer to a security runbook:

• Drop noise before you spend tokens (YAML filters)
• Declare the graph in YAML so a team can change stages without a Python deploy
• Treat low confidence as a halt, not a vibe
• Plan mode that physically cannot push a branch (stop_before)
• Reviewers that run in parallel with no shared chat, so they cannot rubber-stamp each other
• Every prompt and completion stored so you can replay a decision in a postmortem

The reference consumer is CVE / SAST / ADO remediation. The core library does not know what a CVE is on purpose.

If you work on agent orchestration: the interesting debate is not “which demo writes more code.” It is who owns the graph, who can stop side effects, and whether two reviewers are actually independent.

Repo: experimental. No SLA. Clone it, break it, steal the ADRs.
```

### Longer article post (split into 2–3 LinkedIn articles or a newsletter)

**Headline:** Stop asking agents to be employees. Ask them to be stages in a runbook.

**Opening.** The industry is shipping two genres of “agents.” Genre A is the autonomous engineer (Devin and siblings): give it a repo and a ticket. Genre B is the simulated org (MetaGPT and role crews): give it a PRD and watch roles pass artifacts down an SOP. Both are legitimate. Neither is what I needed when I pictured a security finding landing in a queue.

**The third genre.** A finding is not a blank page. It is an object with severity, repo, and source. Most of them should never touch an LLM. The ones that should must be planned, challenged by a second model, and forbidden from git until a human says so. That is orchestration with policy, not a clever system prompt.

**Design choices (each a paragraph you can cut).**  
YAML graph so topology is visible. Filter engine with zero token cost. Confidence retry then escalate. Parallel adversarial review without a shared transcript. Per-call session isolation so agents do not silently inherit another agent’s chat. StubLLM so CI does not need a vendor key. SQLite of prompts because “the model said so” is not an audit.

**What I am not claiming.** This is a PoC. Hardening (scrubbers, mTLS, schema validation) is experimental. I evaluated LangGraph and did not use it as the backbone; that is an opinion, not a verdict that LangGraph is wrong. CrewAI is a better on-ramp for many teams. Devin is a better coder-in-a-box.

**Close.** If you are building agents for production-shaped work, write down whether your reviewers can see each other, whether plan mode is a prompt or a graph property, and whether you can replay last Tuesday’s run. That is the experiment AgenticConductor is running in public.

---

## Quote cards (optional graphics)

- “Plan mode that cannot push a branch is a graph property, not a prompt.”
- “If two reviewers share a thread, you do not have two reviewers.”
- “Filters before tokens. Confidence before git. YAML before heroics.”
- “Devin is the engineer. This PoC is trying to be the conductor.”
- “Experiment. Not a product. Steal the ADRs.”

---

## Hashtags and tagging hygiene

Suggested (use sparingly): `#MultiAgent` `#LLMOps` `#AIEngineering` `#DevSecOps` `#OpenSource`

Do **not** tag Cognition, MetaGPT maintainers, or GitHub as if this were a partnership. Do **not** imply endorsement.

---

## Repo links to include

- Overview (developer): repository root `README.md`
- This narrative: `docs/LINKEDIN_PRESENTATION.md`
- Why not LangGraph: `ai-agents/docs/adr/ADR-008-custom-orchestration-vs-langgraph.md`
- Why not group chat: `ai-agents/docs/adr/ADR-005-parallel-runners-not-group-chat.md`
- Plan vs execute: `ai-agents/docs/adr/ADR-006-plan-execute-mode-stop-before.md`
- First run: `cd ai-agents && make setup && make demo-snyk`
