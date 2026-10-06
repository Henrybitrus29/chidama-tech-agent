"""BM25 retrieval with an explicit "can we answer this?" gate.

The gate is the important part. Plain BM25 always returns *something*, so we also measure how much of the
question (weighted by term rarity) is actually covered by the retrieved passages. Question words the
knowledge base has never seen count against coverage, so off-topic questions are refused instead of
answered from a loosely related chunk.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .chunking import Chunk
from .text import tokenize

# Small, generic synonym groups. Tenants can add their own in tenant.json ("synonyms").
DEFAULT_SYNONYMS: list[list[str]] = [
    ["cost", "price", "pricing", "fee", "charge", "rate", "quote", "afford", "expensive"],
    ["hours", "open", "opening", "close", "closing"],
    ["contact", "reach", "email", "phone", "call"],
    ["warranty", "guarantee", "guaranteed"],
    ["appointment", "book", "booking", "consultation", "visit"],
    ["long", "duration", "timeline", "week", "day", "hour"],
]


@dataclass
class Hit:
    chunk: Chunk
    score: float
    coverage: float


@dataclass
class SearchResult:
    hits: list[Hit] = field(default_factory=list)
    answerable: bool = False
    reason: str = "no_match"          # ok | no_match | low_coverage | low_score
    coverage: float = 0.0


def build_synonym_map(groups: list[list[str]]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for group in groups:
        stems = {s for w in group for s in tokenize(w, keep_stopwords=True)}
        for s in stems:
            mapping.setdefault(s, set()).update(stems - {s})
    return mapping


class BM25Index:
    def __init__(
        self,
        chunks: list[Chunk],
        synonyms: dict[str, list[str]] | None = None,
        k1: float = 1.5,
        b: float = 0.75,
        min_coverage: float = 0.5,
        min_score: float = 0.0,
    ):
        self.chunks = list(chunks)
        self.k1, self.b = k1, b
        self.min_coverage, self.min_score = min_coverage, min_score

        self._tf: list[Counter] = []
        self._len: list[int] = []
        df: Counter = Counter()
        for c in self.chunks:
            # headings are repeated so a section title outweighs a passing mention
            tokens = tokenize(c.title) + tokenize(c.heading) * 2 + tokenize(c.text)
            tf = Counter(tokens)
            self._tf.append(tf)
            self._len.append(len(tokens))
            df.update(tf.keys())
        n = len(self.chunks)
        self._avgdl = (sum(self._len) / n) if n else 1.0
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self._avg_idf = (sum(self._idf.values()) / len(self._idf)) if self._idf else 1.0

        groups = [list(g) for g in DEFAULT_SYNONYMS]
        for key, values in (synonyms or {}).items():
            groups.append([key, *values])
        self._syn = build_synonym_map(groups)

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, k: int = 3) -> SearchResult:
        terms = list(dict.fromkeys(tokenize(query)))
        if not terms or not self.chunks:
            return SearchResult(reason="no_match")

        known: list[tuple[list[str], float]] = []
        unknown = 0
        for t in terms:
            members = [t, *sorted(self._syn.get(t, ()))]
            present = [m for m in members if m in self._idf]
            if present:
                known.append((present, max(self._idf[m] for m in present)))
            else:
                unknown += 1
        if not known:
            return SearchResult(reason="no_match")

        denom = sum(w for _, w in known) + unknown * self._avg_idf
        scored: list[tuple[float, int]] = []
        for i, tf in enumerate(self._tf):
            norm = 1 - self.b + self.b * self._len[i] / self._avgdl
            score = 0.0
            for present, _ in known:
                best = 0.0
                for m in present:
                    f = tf.get(m, 0)
                    if f:
                        best = max(best, self._idf[m] * f * (self.k1 + 1) / (f + self.k1 * norm))
                score += best
            if score > 0:
                scored.append((score, i))
        if not scored:
            return SearchResult(reason="no_match")
        scored.sort(key=lambda x: -x[0])
        top = scored[:k]

        def covered(idx: int) -> float:
            tf = self._tf[idx]
            return sum(w for present, w in known if any(m in tf for m in present)) / denom

        hits = [Hit(self.chunks[i], s, covered(i)) for s, i in top]
        # coverage over everything we would hand to the model, since the answer may span two chunks
        union = sum(
            w for present, w in known if any(m in self._tf[i] for _, i in top for m in present)
        ) / denom
        if union < self.min_coverage:
            return SearchResult(hits, False, "low_coverage", union)
        if hits[0].score < self.min_score:
            return SearchResult(hits, False, "low_score", union)
        return SearchResult(hits, True, "ok", union)


class HybridRetriever:
    """BM25 + embeddings, merged with reciprocal-rank fusion. Experimental: tune vector_min_sim with the eval."""

    def __init__(self, bm25: BM25Index, vectors, vector_min_sim: float = 0.72):
        self.bm25, self.vectors, self.vector_min_sim = bm25, vectors, vector_min_sim
        self.chunks = bm25.chunks

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, k: int = 3) -> SearchResult:
        lex = self.bm25.search(query, k=max(k, 5))
        vec = self.vectors.search(query, k=max(k, 5))
        fused: dict[str, float] = {}
        by_id: dict[str, Chunk] = {}
        for rank, hit in enumerate(lex.hits):
            fused[hit.chunk.id] = fused.get(hit.chunk.id, 0) + 1 / (60 + rank)
            by_id[hit.chunk.id] = hit.chunk
        for rank, (chunk, _sim) in enumerate(vec):
            fused[chunk.id] = fused.get(chunk.id, 0) + 1 / (60 + rank)
            by_id[chunk.id] = chunk
        ranked = sorted(fused, key=lambda cid: -fused[cid])[:k]
        top_sim = vec[0][1] if vec else 0.0
        answerable = lex.answerable or top_sim >= self.vector_min_sim
        hits = [Hit(by_id[cid], fused[cid], lex.coverage) for cid in ranked]
        if not hits:
            return SearchResult(reason="no_match")
        return SearchResult(hits, answerable, "ok" if answerable else "low_coverage", lex.coverage)
