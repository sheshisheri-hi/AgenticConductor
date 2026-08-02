"""Historical defect triple index for similar-bug retrieval."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from conductor_integrations.memory.embedder import (
    HashEmbedder,
    blob_from_vector,
    cosine,
    vector_from_blob,
)
from conductor_integrations.memory.models import DefectHit, DefectTriple


class DefectMemory:
    """SQLite-backed similar-defect search over symptom/RC triples."""

    def __init__(self, db_path: Path | str, embedder: HashEmbedder | None = None) -> None:
        self.db_path = Path(db_path)
        self.embedder = embedder or HashEmbedder()

    def build(self, triples: list[DefectTriple]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE triples (
                    id TEXT PRIMARY KEY,
                    symptom TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    component TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    issue_url TEXT NOT NULL,
                    fix_pr TEXT NOT NULL,
                    repos_json TEXT NOT NULL,
                    embedding BLOB NOT NULL
                )
                """
            )
            for t in triples:
                text = f"{t.symptom} {t.root_cause} {t.component}"
                conn.execute(
                    """
                    INSERT INTO triples
                    (id, symptom, root_cause, component, resolution,
                     issue_url, fix_pr, repos_json, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        t.id,
                        t.symptom,
                        t.root_cause,
                        t.component,
                        t.resolution,
                        t.issue_url,
                        t.fix_pr,
                        json.dumps(t.repos),
                        blob_from_vector(self.embedder.embed(text)),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def search_similar(self, query: str, k: int = 3) -> list[DefectHit]:
        if not self.db_path.exists():
            return []
        q_emb = self.embedder.embed(query)
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT id, symptom, root_cause, component, resolution,
                       issue_url, fix_pr, repos_json, embedding
                FROM triples
                """
            ).fetchall()
        finally:
            conn.close()

        hits: list[DefectHit] = []
        for row in rows:
            (
                tid,
                symptom,
                root_cause,
                component,
                resolution,
                issue_url,
                fix_pr,
                repos_json,
                emb_blob,
            ) = row
            score = cosine(q_emb, vector_from_blob(emb_blob))
            if score < 0.12:
                continue
            hits.append(
                DefectHit(
                    triple_id=tid,
                    symptom=symptom,
                    root_cause=root_cause,
                    component=component,
                    resolution=resolution,
                    issue_url=issue_url,
                    fix_pr=fix_pr,
                    repos=json.loads(repos_json),
                    score=round(score, 4),
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
