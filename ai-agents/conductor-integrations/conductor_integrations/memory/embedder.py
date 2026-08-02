"""Deterministic bag-of-hashed-tokens embedder (no external ML deps).

Good enough for educational hybrid retrieval; swap later for real embeddings.
"""

from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class HashEmbedder:
    """Fixed-dimension hashed bag-of-words vectors."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = tokenize(text)
        if not tokens:
            return vec
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True))


def blob_from_vector(vec: list[float]) -> bytes:
    return ",".join(f"{v:.8f}" for v in vec).encode("utf-8")


def vector_from_blob(blob: bytes) -> list[float]:
    if not blob:
        return []
    return [float(x) for x in blob.decode("utf-8").split(",") if x]
