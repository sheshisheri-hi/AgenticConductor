"""RCA payload enrichment — pulls term/defect/ownership into WorkflowContext."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conductor_integrations.memory.defect_index import DefectMemory
from conductor_integrations.memory.loaders import load_ownership, ownership_lookup
from conductor_integrations.memory.term_index import TermIndex


def _work_item_text(payload: dict[str, Any]) -> str:
    item = payload.get("work_item") or {}
    parts = [
        str(item.get("title") or ""),
        str(item.get("description") or ""),
    ]
    meta = item.get("metadata") or {}
    if isinstance(meta, dict):
        parts.append(str(meta.get("reproduction_steps") or ""))
    return "\n".join(p for p in parts if p)


def enrich_rca_payload(
    payload: dict[str, Any],
    *,
    term_index_path: Path | str,
    defect_index_path: Path | str,
    ownership_path: Path | str | None = None,
    k_terms: int = 3,
    k_defects: int = 3,
) -> dict[str, Any]:
    """Mutate and return payload with RCA enrichment fields."""
    text = _work_item_text(payload)
    term_hits = TermIndex(term_index_path).resolve(text, k=k_terms)
    defect_hits = DefectMemory(defect_index_path).search_similar(text, k=k_defects)

    components = [h.component for h in term_hits if h.component]
    for h in defect_hits:
        if h.component:
            components.append(h.component)

    candidate_repos: list[str] = []
    for h in term_hits:
        candidate_repos.extend(h.repos)
    for h in defect_hits:
        candidate_repos.extend(h.repos)

    ownership: dict[str, Any] = {
        "matched_components": [],
        "owners": [],
        "repos": [],
        "teams": [],
    }
    if ownership_path and Path(ownership_path).exists():
        ownership = ownership_lookup(load_ownership(ownership_path), components)
        candidate_repos.extend(ownership.get("repos") or [])

    # de-dupe repos
    seen: set[str] = set()
    repos_unique: list[str] = []
    for r in candidate_repos:
        if r and r not in seen:
            seen.add(r)
            repos_unique.append(r)

    payload["term_hits"] = [h.model_dump() for h in term_hits]
    payload["similar_defects"] = [h.model_dump() for h in defect_hits]
    payload["candidate_repos"] = repos_unique
    payload["owners"] = ownership.get("owners") or []
    payload["ownership"] = ownership
    payload["rca_enriched"] = True
    return payload


def format_rca_context_for_prompt(payload: dict[str, Any]) -> str:
    """Human-readable block for prompt templates."""
    if not payload.get("rca_enriched"):
        return "RCA enrichment not available."

    lines: list[str] = []
    terms = payload.get("term_hits") or []
    if terms:
        lines.append("### Resolved product terms")
        for t in terms:
            lines.append(
                f"- {t.get('canonical')} (component={t.get('component')}, "
                f"repos={t.get('repos')}, score={t.get('score')}, via={t.get('matched_via')})"
            )
    defects = payload.get("similar_defects") or []
    if defects:
        lines.append("### Similar historical defects")
        for d in defects:
            lines.append(
                f"- [{d.get('triple_id')}] symptom={d.get('symptom')!r} "
                f"| root_cause={d.get('root_cause')!r} "
                f"| resolution={d.get('resolution')!r} "
                f"| url={d.get('issue_url')} score={d.get('score')}"
            )
    repos = payload.get("candidate_repos") or []
    if repos:
        lines.append("### Candidate repos")
        lines.append("- " + ", ".join(repos))
    owners = payload.get("owners") or []
    if owners:
        lines.append("### Owners")
        lines.append("- " + ", ".join(owners))
    lines.append(
        "\nYou MUST cite resolved terms and similar defects as evidence. "
        "Only plan changes inside candidate_repos. If repos are unknown, set requires_human=true."
    )
    return "\n".join(lines) if lines else "RCA enrichment returned no hits."


def maybe_enrich_rca(context: Any) -> bool:
    """Enrich context.payload if rca_memory config is present. Returns True if ran."""
    payload = context.payload
    cfg = payload.get("rca_memory") or {}
    if not cfg:
        return False
    if payload.get("rca_enriched") and not cfg.get("force"):
        return False
    term_path = cfg.get("term_index")
    defect_path = cfg.get("defect_index")
    if not term_path or not defect_path:
        return False
    enrich_rca_payload(
        payload,
        term_index_path=term_path,
        defect_index_path=defect_path,
        ownership_path=cfg.get("ownership"),
        k_terms=int(cfg.get("k_terms", 3)),
        k_defects=int(cfg.get("k_defects", 3)),
    )
    # Keep a compact JSON string for prompts that want it
    payload["rca_context"] = format_rca_context_for_prompt(payload)
    payload["rca_context_json"] = json.dumps(
        {
            "term_hits": payload.get("term_hits"),
            "similar_defects": payload.get("similar_defects"),
            "candidate_repos": payload.get("candidate_repos"),
            "owners": payload.get("owners"),
        },
        indent=2,
    )
    return True
