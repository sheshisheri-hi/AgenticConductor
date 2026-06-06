# Multi-Agent Workflow Conductor Sample

**Time to build:** ~10 hours  
**Level:** Intermediate  
**Purpose:** Demonstrate parallel processing, context passing, result aggregation, and `FilterEngine` filtering.

---

## Workflow Overview

This sample shows how a Conductor workflow can fetch data once, then fan out work across multiple agents:

1. `fetcher` returns 10-20 mock items.
2. `processor_a` and `processor_b` run for every item.
3. `aggregator` merges both result streams.
4. `FilterEngine` keeps only items at or above the requested priority.
5. Results are sorted by the combined score.

The sample also measures sequential versus parallel execution so the benefit is visible from a single run.

---

## Why Parallel Execution Helps

Each processor sleeps briefly to simulate I/O or LLM latency. In sequential mode, every item waits for both processors one after the other. In parallel mode, `asyncio.gather()` allows both processors to run at the same time per item, and all items are scheduled together.

Expected outcome:

- lower end-to-end latency
- same deterministic output shape
- clearer fan-out / fan-in orchestration pattern

---

## File Structure

```
multi-agent-workflow/
├── conductor.json
├── main.py
├── agents/
│   ├── fetcher.py
│   ├── processor_a.py
│   ├── processor_b.py
│   └── aggregator.py
├── logs/                 # created on first run
└── README.md
```

---

## Run It

```bash
cd multi-agent-workflow

python main.py --plan
python main.py
python main.py --item-count 16
python main.py --priority-threshold medium
python main.py --help
```

Example output:

```text
Fetched items: 12
Sequential time: 0.842s
Parallel time:   0.116s
Filtered results: 6
```

---

## How FilterEngine Is Used

`aggregator.py` imports `FilterEngine` from `conductor_core.filter_engine` and applies two rules:

1. reject anything below the requested priority threshold
2. reject duplicates by `id`

This mirrors the broader Conductor approach: obvious filtering should happen before expensive downstream work.

---

## Extending the Sample

Good next steps for a consumer-showcase enhancement:

- replace `fetcher` with real service calls
- feed processor outputs into a router or planner stage
- add more processor variants for A/B ranking
- persist timing metrics in SQLite or OTEL traces
- turn aggregator output into tickets, dashboards, or patch plans

---

## Reference Value

This sample is useful when you want to explain:

- fan-out / fan-in orchestration
- context propagation between agents
- deterministic filtering before human review
- how stub workflows can still prove concurrency value
