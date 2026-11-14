"""Smoke-test the local embedding model: load offline, embed, compute similarity.

Usage:
    python scripts/check_embeddings.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Windows console defaults to cp1252 and crashes printing Vietnamese text.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from embeddings import MyEmbedder  # noqa: E402


def main() -> None:
    embedder = MyEmbedder()
    print(f"Model:  {embedder.model_name}")
    print(f"Dimensions: {embedder.dimensions}")

    docs = [
        "Quy trình nạp dữ liệu gồm các bước: đọc tài liệu, làm sạch, chia chunk, tạo vector và lưu vào database.",
        "PostgreSQL pgvector hỗ trợ lưu vector và truy vấn tương đồng cosine nhanh.",
        "Hà Nội là thủ đô của Việt Nam, nổi tiếng với Hồ Gươm và phố cổ.",
    ]
    doc_vectors = embedder.embed_documents(docs)
    assert len(doc_vectors) == len(docs), "must return one vector per document"

    query_vec = embedder.embed_query("Làm sao để chia nhỏ tài liệu thành các chunk?")

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))  # vectors are normalized

    scores = [cosine(query_vec, dv) for dv in doc_vectors]
    ranked = sorted(range(len(docs)), key=lambda i: -scores[i])
    print("\nQuery: 'Làm sao để chia nhỏ tài liệu thành các chunk?'")
    for rank, i in enumerate(ranked, 1):
        print(f"  {rank}. score={scores[i]:.4f}  {docs[i][:60]}...")

    assert ranked[0] == 0, "expected the chunking passage to rank first"
    norm = sum(x * x for x in query_vec) ** 0.5
    assert abs(norm - 1.0) < 1e-3, f"vectors must be normalized, got norm={norm:.4f}"
    print("\nOK: model loads locally, embeds correctly, vectors normalized.")


if __name__ == "__main__":
    main()
