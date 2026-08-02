"""Tests for issue export schema + heuristic triple extraction."""

from __future__ import annotations

import json
from pathlib import Path

from conductor_integrations.memory.export_issues import normalize_ado_work_item, write_issues_raw
from conductor_integrations.memory.extract_triples import extract_triples, heuristic_triple_from_issue


def test_heuristic_triple_from_github_issue():
    t = heuristic_triple_from_issue(
        {
            "id": "42",
            "source": "github",
            "title": "Panels stuck after time range change",
            "body": "Timeouts on Prometheus.\n\nFix: raise timeout and cancel queries.",
            "html_url": "https://github.com/grafana/grafana/issues/42",
            "repo": "grafana/grafana",
            "labels": ["datasource"],
        }
    )
    assert t.id == "GH-42"
    assert "Panels stuck" in t.symptom
    assert t.repos == ["grafana/grafana"]
    assert t.component == "datasource"


def test_extract_triples_roundtrip(tmp_path: Path):
    raw = {
        "items": [
            {
                "id": "1",
                "source": "github",
                "title": "Freeze on refresh",
                "body": "Overlapping queries.",
                "html_url": "https://example/1",
                "repo": "grafana/grafana",
                "labels": [],
            }
        ]
    }
    inp = tmp_path / "issues_raw.json"
    inp.write_text(json.dumps(raw), encoding="utf-8")
    triples = extract_triples(inp)
    assert len(triples) == 1
    assert triples[0].symptom.startswith("Freeze")


def test_normalize_ado_work_item():
    item = normalize_ado_work_item(
        {
            "id": 99,
            "fields": {
                "System.Title": "ADO bug",
                "System.Description": "desc",
                "System.State": "Closed",
            },
            "url": "https://dev.azure.com/x/_workitems/edit/99",
        },
        repo="my-repo",
    )
    assert item["id"] == "99"
    assert item["source"] == "ado"
    assert item["title"] == "ADO bug"


def test_write_issues_raw(tmp_path: Path):
    out = write_issues_raw(tmp_path / "out.json", [{"id": "1", "title": "t"}], source="github")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["count"] == 1
    assert data["source"] == "github"
