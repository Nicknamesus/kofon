"""Embeddings — pluggable provider with three backends.

Why pluggable: Kofon operates from China, so OpenAI's `text-embedding-3-small`
is off the table (see `memory/project-china-llm-constraint.md`). Two real
options exist — local BGE-M3 via `sentence-transformers`, or Alibaba's
DashScope `text-embedding-v3` API. A deterministic `hash` provider is also
included as a zero-config fallback so smoke tests and CI don't have to
download a 2 GB model or hold an API key.

All providers emit 1024-dim float32 vectors. BGE-M3 is natively 1024;
DashScope text-embedding-v3 is asked for `dimension=1024`; the hash
provider is constructed to be exactly that.

Configure via env (see `app/config.py`):

    EMBEDDING_PROVIDER=hash       # default — non-semantic, deterministic
    EMBEDDING_PROVIDER=bge-m3     # requires `sentence-transformers`
    EMBEDDING_PROVIDER=dashscope  # requires DASHSCOPE_API_KEY

Provider is a process-wide singleton; first call constructs it.
"""

from __future__ import annotations

import hashlib
import os
from typing import Protocol

import httpx

EMBEDDING_DIM = 1024


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


# ---------------- hash (deterministic, non-semantic) ----------------


class HashEmbeddings:
    """SHA-based pseudo-embedding. Same text → same vector; different
    texts → different vectors. Not semantic — only useful when you need
    the pipeline to *work* (uniqueness, dedup, index round-trips) without
    a real model.

    Each output is L2-normalised so cosine distance is well-defined.
    """

    name = "hash"
    dim = EMBEDDING_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        # Expand 32-byte SHA-256 → dim floats via repeated hashing.
        out: list[float] = []
        seed = text.encode("utf-8")
        counter = 0
        while len(out) < self.dim:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            for i in range(0, len(digest), 2):
                if len(out) >= self.dim:
                    break
                # Map two bytes → [-1, 1]
                val = int.from_bytes(digest[i:i + 2], "big") / 32767.5 - 1.0
                out.append(val)
            counter += 1
        # L2 normalise.
        norm = sum(v * v for v in out) ** 0.5 or 1.0
        return [v / norm for v in out]


# ---------------- BGE-M3 (local, sentence-transformers) ----------------


class BGEM3Embeddings:
    """Local BGE-M3 via `sentence-transformers`. Native 1024-dim.

    First call downloads the model (~2 GB) into the HuggingFace cache.
    Subsequent runs reuse it. CPU is fine for our seed sizes.
    """

    name = "bge-m3"
    dim = EMBEDDING_DIM

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "EMBEDDING_PROVIDER=bge-m3 requires `pip install "
                "sentence-transformers` — or switch to `dashscope`/`hash`."
            ) from exc
        self._model = SentenceTransformer("BAAI/bge-m3")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # sentence-transformers is sync — run in a thread to keep the loop free.
        import asyncio

        def _encode() -> list[list[float]]:
            arr = self._model.encode(
                texts, normalize_embeddings=True, convert_to_numpy=True
            )
            return [list(map(float, v)) for v in arr]

        return await asyncio.to_thread(_encode)


# ---------------- DashScope (Alibaba, hosted in China) ----------------


class DashScopeEmbeddings:
    """Qwen `text-embedding-v3` via DashScope. Requires `DASHSCOPE_API_KEY`."""

    name = "dashscope"
    dim = EMBEDDING_DIM
    _endpoint = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    def __init__(self) -> None:
        self._key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not self._key:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=dashscope requires DASHSCOPE_API_KEY."
            )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # DashScope caps a single call at 25 inputs.
        out: list[list[float]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for start in range(0, len(texts), 25):
                batch = texts[start:start + 25]
                resp = await client.post(
                    self._endpoint,
                    headers={
                        "Authorization": f"Bearer {self._key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "text-embedding-v3",
                        "input": {"texts": batch},
                        "parameters": {"dimension": EMBEDDING_DIM},
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                for emb in payload["output"]["embeddings"]:
                    out.append(emb["embedding"])
        return out


# ---------------- factory ----------------


_provider: EmbeddingProvider | None = None


def get_provider() -> EmbeddingProvider:
    """Return the configured provider (cached after first call)."""
    global _provider
    if _provider is not None:
        return _provider

    from app.config import get_settings

    name = (get_settings().embedding_provider or "hash").lower()
    if name == "hash":
        _provider = HashEmbeddings()
    elif name in {"bge-m3", "bgem3", "bge"}:
        _provider = BGEM3Embeddings()
    elif name in {"dashscope", "qwen"}:
        _provider = DashScopeEmbeddings()
    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER={name!r}. "
            "Use 'hash', 'bge-m3', or 'dashscope'."
        )
    return _provider


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convenience wrapper used by the seed loader and tools."""
    if not texts:
        return []
    return await get_provider().embed(texts)


def text_hash(text: str) -> str:
    """16-char SHA-1 of normalized text. Used to skip unchanged re-embeds."""
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:16]
