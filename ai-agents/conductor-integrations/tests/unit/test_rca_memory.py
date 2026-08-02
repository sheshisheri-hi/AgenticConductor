"""Tests for RCA term/defect memory indexes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conductor_integrations.memory.builders import build_defect_index, build_term_index
from conductor_integrations.memory.defect_index import DefectMemory
from conductor_integrations.memory.enrich import enrich_rca_payload, maybe_enrich_rca
from conductor_integrations.memory.term_index import TermIndex

PACK = Path(__file__).resolve().parents[3] / "samples" / "projects" / "grafana-rca"


@pytest.fixture(scope="module")
def built_indexes(tmp_path_factory):
    root = tmp_path_factory.mktemp("rca")
    term_db = root / "term_index.sqlite"
    defect_db = root / "defect_index.sqlite"
    build_term_index(PACK / "docs" / "glossary.yaml", term_db)
    build_defect_index(PACK / "data" / "triples.json", defect_db)
    return term_db, defect_db


def test_resolve_terms_maps_nl_to_product_terms(built_indexes):
    term_db, _ = built_indexes
    hits = TermIndex(term_db).resolve(
        "charts freeze after changing time range on the graphs page",
        k=4,
    )
    assert hits
    ids = {h.term_id for h in hits}
    # Should hit time range / refresh / timeout / dashboard-ish terms
    assert ids & {"time_range", "timeout", "dashboard", "refresh", "panel"}


def test_similar_defects_finds_timeout_freeze(built_indexes):
    _, defect_db = built_indexes
    hits = DefectMemory(defect_db).search_similar(
        "Charts freeze after changing time range",
        k=3,
    )
    assert hits
    ids = {h.triple_id for h in hits}
    assert ids & {"GF-1001", "GF-1002", "GF-1005", "GF-1006"}


def test_enrich_payload_sets_repos_and_owners(built_indexes):
    term_db, defect_db = built_indexes
    payload = {
        "work_item": json.loads((PACK / "data" / "work_item.json").read_text(encoding="utf-8"))
    }
    enrich_rca_payload(
        payload,
        term_index_path=term_db,
        defect_index_path=defect_db,
        ownership_path=PACK / "docs" / "ownership.yaml",
    )
    assert payload["rca_enriched"] is True
    assert "grafana/grafana" in payload["candidate_repos"]
    assert payload["term_hits"]
    assert payload["similar_defects"]
    assert payload["owners"]


def test_maybe_enrich_rca_uses_config(built_indexes):
    term_db, defect_db = built_indexes

    class Ctx:
        def __init__(self):
            self.payload = {
                "work_item": {
                    "title": "panels stuck loading spinner forever",
                    "description": "prometheus datasource hangs",
                },
                "rca_memory": {
                    "term_index": str(term_db),
                    "defect_index": str(defect_db),
                    "ownership": str(PACK / "docs" / "ownership.yaml"),
                },
            }

    ctx = Ctx()
    assert maybe_enrich_rca(ctx) is True
    assert ctx.payload["rca_enriched"] is True
    assert "rca_context" in ctx.payload
