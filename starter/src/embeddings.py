"""Local embedding providers backed by sentence-transformers.

Two selectable models (EMBEDDING_PRESET env or constructor arg):
- "gemma2" (default): google/embeddinggemma-2, 740M params, 768 dims.
  Uses Google's task prompts — asymmetric retrieval:
    queries   -> "task: search result | query: ..."
    documents -> "title: none | text: ..."
  float32 on CPU (float16 is unsupported by EmbeddingGemma 2 activations).
- "minilm": sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, 384 dims.

Vectors are L2-normalized so cosine similarity equals the dot product, which is
what pgvector's vector_cosine_ops expects. Changing the model changes the
dimensions — drop/recreate the store table before re-ingesting.
"""
import os
from pathlib import Path
from typing import Protocol

from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parents[1]

PRESETS = {
    "gemma2": {
        "model_id": "google/embeddinggemma-2",
        "local_dir": BASE_DIR / "models" / "embeddinggemma-2",
        "query_prompt": "Retrieval-query",
        "document_prompt": "Retrieval-document",
        "batch_size": 16,
        "model_kwargs": {"torch_dtype": "float32"},
        "config_kwargs": {"vision_config": None, "audio_config": None},
    },
    "minilm": {
        "model_id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "local_dir": BASE_DIR / "models" / "paraphrase-multilingual-MiniLM-L12-v2",
        "query_prompt": None,
        "document_prompt": None,
        "batch_size": 32,
        "model_kwargs": {},
        "config_kwargs": {},
    },
}


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Embedder running a local sentence-transformers model fully offline."""

    def __init__(self, preset: str | None = None) -> None:
        key = (preset or os.environ.get("EMBEDDING_PRESET") or "gemma2").lower()
        spec = PRESETS.get(key)
        if spec is None:
            raise ValueError(f"unknown embedding preset: {key!r} (choose from {sorted(PRESETS)})")
        self.preset = key
        self.spec = spec

        load_kwargs: dict = {
            "device": "cpu",
            "model_kwargs": spec["model_kwargs"],
            "config_kwargs": spec["config_kwargs"],
        }
        local_dir = spec["local_dir"]
        if local_dir.exists():
            # Local snapshot: no network needed.
            self._model = SentenceTransformer(str(local_dir), **load_kwargs)
        else:
            # Fall back to the model id (uses the shared HF cache).
            self._model = SentenceTransformer(spec["model_id"], **load_kwargs)
        self.model_name = spec["model_id"]
        self.dimensions = self._model.get_sentence_embedding_dimension()
        self._batch_size = spec["batch_size"]

    def _encode(self, texts: list[str], prompt_name: str | None) -> list[list[float]]:
        if not texts:
            return []
        kwargs: dict = {"batch_size": self._batch_size, "normalize_embeddings": True, "show_progress_bar": False}
        if prompt_name and prompt_name in getattr(self._model, "prompts", {}):
            kwargs["prompt_name"] = prompt_name
        vectors = self._model.encode(texts, **kwargs)
        return [v.tolist() for v in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, self.spec["document_prompt"])

    def embed_query(self, question: str) -> list[float]:
        return self._encode([question], self.spec["query_prompt"])[0]
