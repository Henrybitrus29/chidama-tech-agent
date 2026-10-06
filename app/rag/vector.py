"""Optional dense retrieval. Needs numpy; the default embedder needs `fastembed` (ONNX, no PyTorch)."""
from __future__ import annotations

from .chunking import Chunk


class FastEmbedder:
    """Wraps fastembed's TextEmbedding. The model downloads once on first use."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model)

    def embed(self, texts: list[str]):
        import numpy as np

        vectors = np.array(list(self._model.embed(texts)), dtype="float32")
        return vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9)


class VectorIndex:
    def __init__(self, chunks: list[Chunk], embedder):
        self.chunks = list(chunks)
        self.embedder = embedder
        texts = [f"{c.title}. {c.heading}. {c.text}" for c in self.chunks]
        self._matrix = embedder.embed(texts) if texts else None

    def search(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        if self._matrix is None or not query.strip():
            return []
        q = self.embedder.embed([query])[0]
        sims = self._matrix @ q
        order = sims.argsort()[::-1][:k]
        return [(self.chunks[int(i)], float(sims[int(i)])) for i in order]
