"""Store and search vectors using PostgreSQL + pgvector (psycopg 3).

One table holds every strategy; rows are keyed by chunk_id so re-ingesting
never duplicates, and obsolete chunks of changed documents are removed.
Search filters permitted metadata in SQL (jsonb containment) and ranks by
cosine distance. All user-supplied values are parameterized.
"""
import json
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .models import Chunk

# Vector literal for pgvector: '[0.1,0.2,...]' cast with ::vector in SQL.
def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"

def _jsonb_filter(filters: dict[str, Any]) -> str:
    """jsonb containment for a single-key filter; type-safe (10 vs "10" differ)."""
    return json.dumps(filters, ensure_ascii=False)


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not isinstance(dimensions, int) or dimensions <= 0 or dimensions > 16000:
            raise ValueError(f"invalid embedding dimensions: {dimensions!r}")
        self._conninfo = database_url
        self.dimensions = dimensions
        self.table = "chunks"
        self._conn: psycopg.Connection | None = None

    # -- connection ---------------------------------------------------------

    def _connection(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._conninfo, row_factory=dict_row, autocommit=True)
        return self._conn

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()

    # -- schema -------------------------------------------------------------

    def create_schema(self) -> None:
        conn = self._connection()
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                chunk_id    TEXT PRIMARY KEY,
                strategy    TEXT NOT NULL,
                document_id TEXT NOT NULL,
                source      TEXT NOT NULL,
                page        INTEGER NOT NULL,
                text        TEXT NOT NULL,
                metadata    JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                embedding   vector({self.dimensions}) NOT NULL
            )
            """
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {self.table}_strategy_doc_idx ON {self.table} (strategy, document_id)"
        )
        # Small corpora scan fine, but an HNSW index keeps top-k cheap as data grows.
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {self.table}_embedding_hnsw
            ON {self.table} USING hnsw (embedding vector_cosine_ops)
            """
        )

    # -- write --------------------------------------------------------------

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Insert/update chunks for one strategy; drop obsolete ones.

        Chunks belonging to documents being re-ingested but missing from the
        incoming set are deleted, so changed sources never leave stale vectors.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"chunks/vectors length mismatch: {len(chunks)} vs {len(vectors)}")
        for i, vector in enumerate(vectors):
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"vector {i} has {len(vector)} dims, model/store expects {self.dimensions}"
                )
        conn = self._connection()
        with conn.transaction():
            incoming_ids = [c.chunk_id for c in chunks]
            document_ids = sorted({c.document_id for c in chunks})
            if document_ids:
                conn.execute(
                    f"""
                    DELETE FROM {self.table}
                    WHERE strategy = %s AND document_id = ANY(%s) AND chunk_id <> ALL(%s)
                    """,
                    (strategy, document_ids, incoming_ids),
                )
            rows = [
                (
                    chunk.chunk_id,
                    strategy,
                    chunk.document_id,
                    chunk.source,
                    chunk.page,
                    chunk.text,
                    json.dumps(chunk.metadata, ensure_ascii=False),
                    _vector_literal(vector),
                )
                for chunk, vector in zip(chunks, vectors)
            ]
            conn.cursor().executemany(
                f"""
                INSERT INTO {self.table}
                    (chunk_id, strategy, document_id, source, page, text, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    strategy    = EXCLUDED.strategy,
                    document_id = EXCLUDED.document_id,
                    source      = EXCLUDED.source,
                    page        = EXCLUDED.page,
                    text        = EXCLUDED.text,
                    metadata    = EXCLUDED.metadata,
                    embedding   = EXCLUDED.embedding
                """,
                rows,
            )

    # -- read ---------------------------------------------------------------

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Top-k nearest chunks of a strategy; optional metadata filter in SQL.

        Returns chunk ID, text, cosine similarity score and metadata. Filter
        values are parameterized as jsonb containment (exact type match).
        """
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"query vector has {len(query_vector)} dims, store expects {self.dimensions}"
            )
        if top_k <= 0:
            return []
        literal = _vector_literal(query_vector)
        sql = f"""
            SELECT chunk_id, strategy, document_id, source, page, text, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM {self.table}
            WHERE strategy = %s
        """
        params: list[Any] = [literal, strategy]
        for key, value in (filters or {}).items():
            sql += " AND metadata @> %s::jsonb"
            params.append(_jsonb_filter({key: value}))
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params += [literal, top_k]
        rows = self._connection().execute(sql, params).fetchall()
        return [
            {
                "chunk_id": row["chunk_id"],
                "strategy": row["strategy"],
                "document_id": row["document_id"],
                "source": row["source"],
                "page": row["page"],
                "text": row["text"],
                "metadata": row["metadata"],
                "score": float(row["score"]),
            }
            for row in rows
        ]

    def count(self, strategy: str | None = None) -> int:
        """Number of stored chunks, optionally for one strategy."""
        sql = f"SELECT count(*) AS n FROM {self.table}"
        params: list[Any] = []
        if strategy is not None:
            sql += " WHERE strategy = %s"
            params.append(strategy)
        return int(self._connection().execute(sql, params).fetchone()["n"])
