"""Download the embedding model once so it can be used fully offline afterwards.

Usage:
    python scripts/download_model.py                     # default model
    python scripts/download_model.py --model gemma2     # EmbeddingGemma 2
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer

MODELS = {
    "minilm": {
        "id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dir": "paraphrase-multilingual-MiniLM-L12-v2",
        "config_kwargs": {},
    },
    "gemma2": {
        "id": "google/embeddinggemma-2",
        "dir": "embeddinggemma-2",
        # text-only workflow: skip vision/audio encoders (saves ~270M params)
        "config_kwargs": {"vision_config": None, "audio_config": None},
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), default="gemma2")
    args = parser.parse_args()
    spec = MODELS[args.model]

    local_dir = Path(__file__).resolve().parents[1] / "models" / spec["dir"]
    print(f"Downloading {spec['id']} -> {local_dir}")
    model = SentenceTransformer(
        spec["id"],
        device="cpu",
        model_kwargs={"torch_dtype": "float32"},  # float16 unsupported on EmbeddingGemma 2
        config_kwargs=spec["config_kwargs"],
    )
    model.save(str(local_dir))
    print(f"Saved. Dimensions: {model.get_sentence_embedding_dimension()}")
    print(f"Done. Load later with SentenceTransformer(r'{local_dir}').")


if __name__ == "__main__":
    main()
