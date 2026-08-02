"""Hybrid terminology index (alias boost + hashed semantic similarity)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from conductor_integrations.memory.embedder import (
    HashEmbedder,
    blob_from_vector,
    cosine,
    tokenize,
    vector_from_blob,
)
from conductor_integrations.memory.models import TermCard, TermHit


class TermIndex:
    """SQLite-backed hybrid term resolver."""

    def __init__(self, db_path: Path | str, embedder: HashEmbedder | None = None) -> None:
        self.db_path = Path(db_path)
        self.embedder = embedder or HashEmbedder()

    def build(self, terms: list[TermCard]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE terms (
                    id TEXT PRIMARY KEY,
                    canonical TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    plain_language TEXT NOT NULL,
                    component TEXT NOT NULL,
                    repos_json TEXT NOT NULL,
                    code_hints_json TEXT NOT NULL,
                    search_text TEXT NOT NULL,
                    embedding BLOB NOT NULL
                )
                """
            )
            for term in terms:
                search_text = " ".join(
                    [
                        term.canonical,
                        term.plain_language,
                        term.component,
                        *term.aliases,
                        *term.code_hints,
                    ]
                )
                emb = self.embedder.embed(search_text)
                conn.execute(
                    """
                    INSERT INTO terms
                    (id, canonical, aliases_json, plain_language, component,
                     repos_json, code_hints_json, search_text, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        term.id,
                        term.canonical,
                        json.dumps(term.aliases),
                        term.plain_language,
                        term.component,
                        json.dumps(term.repos),
                        json.dumps(term.code_hints),
                        search_text,
                        blob_from_vector(emb),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def resolve(self, query: str, k: int = 3) -> list[TermHit]:
        if not self.db_path.exists():
            return []
        q_tokens = set(tokenize(query))
        q_emb = self.embedder.embed(query)
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT id, canonical, aliases_json, component, repos_json, embedding FROM terms"
            ).fetchall()
        finally:
            conn.close()

        scored: list[TermHit] = []
        for term_id, canonical, aliases_json, component, repos_json, emb_blob in rows:
            aliases = json.loads(aliases_json)
            repos = json.loads(repos_json)
            alias_score = 0.0
            matched_alias = ""
            for alias in [canonical, *aliases]:
                alias_toks = set(tokenize(alias))
                if not alias_toks:
                    continue
                # Exact phrase or token overlap boost
                if alias.lower() in query.lower():
                    alias_score = max(alias_score, 1.0)
                    matched_alias = alias
                else:
                    overlap = len(q_tokens & alias_toks) / max(len(alias_toks), 1)
                    if overlap > alias_score:
                        alias_score = overlap
                        matched_alias = alias
            sem = cosine(q_emb, vector_from_blob(emb_blob))
            # Hybrid: strong weight on alias, semantic as backup
            score = 0.65 * alias_score + 0.35 * max(sem, 0.0)
            if score < 0.15:
                continue
            via = "both" if alias_score > 0.2 and sem > 0.2 else (
                "alias" if alias_score >= sem else "semantic"
            )
            scored.append(
                TermHit(
                    term_id=term_id,
                    canonical=canonical,
                    component=component,
                    repos=repos,
                    score=round(score, 4),
                    matched_via=f"{via}:{matched_alias}" if matched_alias else via,
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]
