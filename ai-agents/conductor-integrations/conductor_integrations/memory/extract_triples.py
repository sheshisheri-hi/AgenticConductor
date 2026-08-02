"""Extract symptom/root_cause/resolution triples from issues_raw.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from conductor_integrations.memory.models import DefectTriple


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def heuristic_triple_from_issue(item: dict[str, Any]) -> DefectTriple:
    """Rule-based extraction good enough for bootstrap / offline demos."""
    title = (item.get("title") or "").strip()
    body = _strip_html(item.get("body") or "")
    iid = str(item.get("id") or "unknown")
    repo = item.get("repo") or ""
    url = item.get("html_url") or ""

    # Prefer first substantial paragraph as root-cause guess; title as symptom
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
    root = paragraphs[0][:400] if paragraphs else "Unknown — needs manual RCA review"
    resolution = ""
    for p in paragraphs[1:]:
        low = p.lower()
        if any(k in low for k in ("fix", "resolve", "workaround", "patch", "merged")):
            resolution = p[:400]
            break
    if not resolution and paragraphs:
        resolution = "See issue discussion / linked PR"

    labels = item.get("labels") or []
    component = ""
    if isinstance(labels, list) and labels:
        component = str(labels[0])

    return DefectTriple(
        id=f"GH-{iid}" if item.get("source") == "github" else f"ADO-{iid}",
        symptom=title or body[:200] or f"issue {iid}",
        root_cause=root,
        component=component,
        resolution=resolution,
        issue_url=url,
        fix_pr="",
        repos=[repo] if repo else [],
    )


def extract_triples(
    issues_raw_path: Path | str,
    *,
    limit: int | None = None,
) -> list[DefectTriple]:
    raw = json.loads(Path(issues_raw_path).read_text(encoding="utf-8"))
    items = raw.get("items", raw if isinstance(raw, list) else [])
    if limit is not None:
        items = items[:limit]
    return [heuristic_triple_from_issue(it) for it in items]


def write_triples(path: Path | str, triples: list[DefectTriple]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [t.model_dump() for t in triples]
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract defect triples from issues_raw.json")
    parser.add_argument("--in", dest="inp", required=True, help="issues_raw.json path")
    parser.add_argument("--out", required=True, help="triples.json path")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    triples = extract_triples(args.inp, limit=args.limit)
    path = write_triples(args.out, triples)
    print(f"Wrote {len(triples)} triples → {path}")


if __name__ == "__main__":
    main()
