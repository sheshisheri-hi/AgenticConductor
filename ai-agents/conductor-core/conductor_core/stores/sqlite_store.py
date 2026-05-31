"""SQLiteResultStore — default result store for development and testing.

Schema (single table):
    runs (
        run_id       TEXT PRIMARY KEY,
        source       TEXT,                 -- payload.work_item.source (indexed)
        workflow     TEXT,                 -- workflow name from graph
        mode         TEXT,                 -- plan | execute
        blocked      INTEGER,              -- 0 | 1
        blocked_reason TEXT,
        decision_count INTEGER,
        total_tokens  INTEGER,
        total_latency_ms REAL,
        payload_json  TEXT,               -- full WorkflowContext as JSON
        created_at   TEXT                 -- ISO 8601 UTC
        plan_markdown TEXT,
        scribe_output_json TEXT,
        delivery_status TEXT,
        delivery_url TEXT,
        estimated_cost_usd REAL
    )

In production, replace with PostgresResultStore that stores payload_json in a JSONB column
for indexed queries on work_item fields.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from conductor_core.interfaces import IResultStore


def _plan_to_markdown(plan: dict) -> str:
    lines = [f"# Fix Plan\n\n**Summary:** {plan.get('summary', 'N/A')}"]
    lines.append(f"\n**Effort:** {plan.get('estimated_effort', 'N/A')}")
    if plan.get("steps"):
        lines.append("\n## Steps")
        for step in plan["steps"]:
            lines.append(f"- {step}")
    if plan.get("files_to_change"):
        lines.append("\n## Files to Change")
        for f in plan["files_to_change"]:
            if isinstance(f, dict):
                lines.append(f"- `{f.get('path','')}` ({f.get('change_type','')})")
            else:
                lines.append(f"- `{f}`")
    if plan.get("tests_needed"):
        lines.append("\n## Tests Needed")
        for t in plan["tests_needed"]:
            lines.append(f"- {t}")
    return "\n".join(lines)


class SQLiteResultStore(IResultStore):
    """Persists run results to a local SQLite file.

    Args:
        db_path: Path to the SQLite file. Defaults to conductor_runs.db in the
                 current working directory. Pass ":memory:" for in-memory (tests).
    """

    _DDL = """
    CREATE TABLE IF NOT EXISTS runs (
        run_id          TEXT PRIMARY KEY,
        source          TEXT,
        workflow        TEXT,
        mode            TEXT,
        blocked         INTEGER DEFAULT 0,
        blocked_reason  TEXT,
        decision_count  INTEGER DEFAULT 0,
        total_tokens    INTEGER DEFAULT 0,
        total_latency_ms REAL DEFAULT 0.0,
        payload_json    TEXT NOT NULL,
        created_at      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_runs_source ON runs (source);
    CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at);
    CREATE TABLE IF NOT EXISTS agent_decisions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          TEXT NOT NULL,
        agent           TEXT NOT NULL,
        stage           TEXT NOT NULL,
        round           INTEGER NOT NULL DEFAULT 1,
        confidence      REAL NOT NULL,
        recommendation  TEXT NOT NULL,
        requires_human  INTEGER DEFAULT 0,
        reasoning_json  TEXT NOT NULL,
        evidence_json   TEXT NOT NULL,
        concerns_json   TEXT NOT NULL,
        raw_llm_response TEXT,
        prompt_system   TEXT,
        prompt_user     TEXT,
        tokens_used     INTEGER DEFAULT 0,
        latency_ms      REAL DEFAULT 0.0,
        estimated_cost_usd REAL DEFAULT 0.0,
        model_used      TEXT DEFAULT '',
        created_at      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_decisions_run_id ON agent_decisions (run_id);
    """

    def __init__(self, db_path: str | Path = "conductor_runs.db") -> None:
        self._db_path = str(db_path)

    async def _ensure_schema(self, conn: aiosqlite.Connection) -> None:
        for stmt in self._DDL.strip().split(";"):
            if stmt.strip():
                await conn.execute(stmt)
        # Try to add new columns if they don't exist
        for col_def in [
            "ALTER TABLE runs ADD COLUMN plan_markdown TEXT",
            "ALTER TABLE runs ADD COLUMN scribe_output_json TEXT",
            "ALTER TABLE runs ADD COLUMN delivery_status TEXT",
            "ALTER TABLE runs ADD COLUMN delivery_url TEXT",
            "ALTER TABLE runs ADD COLUMN estimated_cost_usd REAL DEFAULT 0.0",
            "ALTER TABLE agent_decisions ADD COLUMN model_used TEXT DEFAULT ''",
        ]:
            try:
                await conn.execute(col_def)
            except Exception:
                pass  # Column already exists
        await conn.commit()

    async def save_run(self, context: Any) -> None:
        """Serialize WorkflowContext and upsert into runs table."""
        payload_json = context.model_dump_json()
        source = (context.payload.get("work_item") or {}).get("source", "")
        workflow = getattr(context, "workflow_name", "")
        now = datetime.now(timezone.utc).isoformat()

        estimated_cost = sum(
            getattr(d, "estimated_cost_usd", 0.0) for d in context.decisions
        )
        fix_plan = context.payload.get("fix_plan")
        plan_markdown = _plan_to_markdown(fix_plan) if fix_plan else None
        scribe_output = context.payload.get("scribe_output")
        scribe_json = json.dumps(scribe_output) if scribe_output else None

        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_schema(conn)
            await conn.execute(
                """
                INSERT INTO runs
                    (run_id, source, workflow, mode, blocked, blocked_reason,
                     decision_count, total_tokens, total_latency_ms, payload_json, created_at,
                     plan_markdown, scribe_output_json, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    workflow        = excluded.workflow,
                    blocked         = excluded.blocked,
                    blocked_reason  = excluded.blocked_reason,
                    decision_count  = excluded.decision_count,
                    total_tokens    = excluded.total_tokens,
                    total_latency_ms = excluded.total_latency_ms,
                    payload_json    = excluded.payload_json,
                    plan_markdown   = excluded.plan_markdown,
                    scribe_output_json = excluded.scribe_output_json,
                    estimated_cost_usd = excluded.estimated_cost_usd
                """,
                (
                    context.run_id,
                    source,
                    workflow,
                    context.mode,
                    1 if context.blocked else 0,
                    context.blocked_reason,
                    len(context.decisions),
                    context.telemetry.total_tokens,
                    context.telemetry.total_latency_ms,
                    payload_json,
                    now,
                    plan_markdown,
                    scribe_json,
                    estimated_cost,
                ),
            )
            await conn.commit()

    async def get_run(self, run_id: str) -> dict | None:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_schema(conn)
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                data = dict(row)
                data["payload"] = json.loads(data.pop("payload_json"))
                return data

    async def list_runs(
        self,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_schema(conn)
            conn.row_factory = aiosqlite.Row
            if source:
                query = (
                    "SELECT run_id, source, workflow, mode, blocked, blocked_reason, "
                    "decision_count, total_tokens, total_latency_ms, created_at, "
                    "estimated_cost_usd, plan_markdown "
                    "FROM runs WHERE source = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
                )
                params = (source, limit, offset)
            else:
                query = (
                    "SELECT run_id, source, workflow, mode, blocked, blocked_reason, "
                    "decision_count, total_tokens, total_latency_ms, created_at, "
                    "estimated_cost_usd, plan_markdown "
                    "FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?"
                )
                params = (limit, offset)

            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def save_decision(self, run_id: str, decision: Any, stage: str) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_schema(conn)
            await conn.execute(
                """
                INSERT INTO agent_decisions (
                    run_id, agent, stage, round, confidence, recommendation, requires_human,
                    reasoning_json, evidence_json, concerns_json, raw_llm_response,
                    prompt_system, prompt_user, tokens_used, latency_ms, estimated_cost_usd,
                    model_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, decision.agent, stage, decision.round, decision.confidence,
                    decision.recommendation, 1 if decision.requires_human else 0,
                    json.dumps(decision.reasoning), json.dumps(decision.evidence),
                    json.dumps(decision.concerns),
                    getattr(decision, "raw_llm_response", ""),
                    getattr(decision, "prompt_system", ""),
                    getattr(decision, "prompt_user", ""),
                    getattr(decision, "tokens_used", 0),
                    getattr(decision, "latency_ms", 0.0),
                    getattr(decision, "estimated_cost_usd", 0.0),
                    getattr(decision, "model_used", ""),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await conn.commit()

    async def get_decisions(self, run_id: str) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_schema(conn)
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM agent_decisions WHERE run_id = ? ORDER BY id", (run_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    d = dict(row)
                    d["reasoning"] = json.loads(d.pop("reasoning_json", "[]"))
                    d["evidence"] = json.loads(d.pop("evidence_json", "[]"))
                    d["concerns"] = json.loads(d.pop("concerns_json", "[]"))
                    results.append(d)
                return results

    async def save_plan_markdown(self, run_id: str, plan_markdown: str) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_schema(conn)
            await conn.execute(
                "UPDATE runs SET plan_markdown = ? WHERE run_id = ?",
                (plan_markdown, run_id),
            )
            await conn.commit()

    async def save_scribe_output(self, run_id: str, scribe_json: str) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_schema(conn)
            await conn.execute(
                "UPDATE runs SET scribe_output_json = ? WHERE run_id = ?",
                (scribe_json, run_id),
            )
            await conn.commit()
