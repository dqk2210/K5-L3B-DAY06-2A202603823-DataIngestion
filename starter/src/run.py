"""Day 06 pipeline entry point.

Orchestrates: corpus load -> chunking strategies -> local embeddings ->
pgvector storage -> benchmark retrieval -> evaluation traces -> summary.

Strategies share the same corpus, embedding model and benchmark; each
comparison changes exactly one factor:

  A_fixed       fixed-size windows, never applies a query filter
  B_para        paragraph groups, never applies a query filter
  C_para_flt    same chunks as B, applies the question's metadata filter

B vs A isolates the chunking factor; C vs B isolates the filter factor.
Questions come from benchmark/questions.jsonl (schema in BENCHMARK.md).
Re-ingesting the same corpus never duplicates rows (store.upsert removes
stale chunk ids), so the pipeline is safe to re-run.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import TOP_K, evaluate_query, summarize
from .ingestion import load_pages_jsonl
from .models import Chunk, DocumentPage
from .store import PgVectorStore

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parents[1]  # starter/
REPO = BASE.parent
DEFAULT_PAGES = REPO / "data" / "extracted" / "pages.jsonl"
DEFAULT_BENCHMARK = REPO / "benchmark" / "questions.jsonl"
RESULTS = BASE / "results"

MIN_CONTENT_PAGES = 30  # lab requirement (GUIDE.md)
MIN_QUESTIONS = 20  # lab requirement (BENCHMARK.md)
MIN_DEV, MIN_TEST = 15, 5
MIN_FILTERED, MIN_FILTERED_TEST = 3, 1

FIXED_SIZE, FIXED_OVERLAP = 1000, 150
PARA_MAX = 1200


def build_chunks(strategy: str, pages: list[DocumentPage]) -> list[Chunk]:
    """Chunk the whole corpus for one strategy; chunk ids get a strategy prefix
    so strategies never collide in the shared store table."""
    if strategy == "A_fixed":
        chunks = [c for p in pages for c in fixed_size(p, FIXED_SIZE, FIXED_OVERLAP)]
    elif strategy == "B_para":
        chunks = [c for p in pages for c in by_paragraph(p, PARA_MAX)]
    elif strategy == "C_para_flt":
        chunks = [c for p in pages for c in by_paragraph(p, PARA_MAX)]
    else:
        raise ValueError(f"unknown strategy: {strategy}")
    for chunk in chunks:
        chunk.chunk_id = f"{strategy}#{chunk.chunk_id}"
        # tag chunks with the full config code so evaluation reports B and C
        # separately (they share the same chunking but differ in filter use)
        chunk.metadata["strategy"] = strategy
    return chunks


def load_benchmark(path: Path, allow_small: bool) -> list[dict]:
    """Load and validate the benchmark per BENCHMARK.md rules."""
    if not path.exists():
        raise SystemExit(
            f"Benchmark not found: {path}\n"
            "Create benchmark/questions.jsonl (>=20 questions, 15 dev / 5 test,\n"
            ">=3 with filter, >=1 filter question in test) — schema in BENCHMARK.md."
        )
    questions = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    ids = [q.get("id") for q in questions]
    if len(set(ids)) != len(ids):
        raise SystemExit("Benchmark has duplicate question ids.")
    required = ("split", "question", "expected_answer", "gold_source_id", "gold_page", "evidence_quote")
    for q in questions:
        missing = [key for key in required if not q.get(key)]
        if missing:
            raise SystemExit(f"Question {q.get('id')} missing fields: {missing}")
    if allow_small:
        print(f"[benchmark] {len(questions)} questions (size/split validation skipped)")
        return questions

    dev = [q for q in questions if q["split"] == "dev"]
    test = [q for q in questions if q["split"] == "test"]
    filtered = [q for q in questions if q.get("filter")]
    filtered_test = [q for q in filtered if q["split"] == "test"]
    problems = []
    if len(questions) < MIN_QUESTIONS:
        problems.append(f"need >= {MIN_QUESTIONS} questions, got {len(questions)}")
    if len(dev) < MIN_DEV:
        problems.append(f"need >= {MIN_DEV} dev, got {len(dev)}")
    if len(test) < MIN_TEST:
        problems.append(f"need >= {MIN_TEST} test, got {len(test)}")
    if len(filtered) < MIN_FILTERED:
        problems.append(f"need >= {MIN_FILTERED} filtered questions, got {len(filtered)}")
    if len(filtered_test) < MIN_FILTERED_TEST:
        problems.append(f"need >= {MIN_FILTERED_TEST} filtered test question, got {len(filtered_test)}")
    if problems:
        raise SystemExit("Benchmark validation failed:\n  - " + "\n  - ".join(problems))
    print(f"[benchmark] OK: {len(questions)} questions ({len(dev)} dev / {len(test)} test, "
          f"{len(filtered)} with filter)")
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 06 ingestion + benchmark pipeline")
    parser.add_argument("--pages", type=Path, default=DEFAULT_PAGES, help="pages.jsonl path")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK, help="questions.jsonl path")
    parser.add_argument(
        "--allow-small-benchmark",
        action="store_true",
        help="skip size/split validation (smoke tests only — never for reported runs)",
    )
    args = parser.parse_args()

    load_dotenv(BASE / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL missing — copy starter/.env.example to starter/.env")

    # 1. corpus -------------------------------------------------------------
    t0 = time.perf_counter()
    pages = load_pages_jsonl(args.pages)
    content_pages = [p for p in pages if p.metadata.get("page_type") == "noi_dung"]
    print(f"[corpus] {len(pages)} pages loaded, {len(content_pages)} content pages "
          f"from {len({p.document_id for p in pages})} documents")
    if len(content_pages) < MIN_CONTENT_PAGES:
        raise SystemExit(f"Corpus too small: {len(content_pages)} content pages < {MIN_CONTENT_PAGES}")

    embedder = MyEmbedder()
    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()
    print(f"[embed] {embedder.model_name} ({embedder.dimensions} dims, local, cost 0 USD)")

    # 2-3. chunk + embed + store per strategy --------------------------------
    strategies = ["A_fixed", "B_para", "C_para_flt"]
    uses_filter = {"A_fixed": False, "B_para": False, "C_para_flt": True}
    strategy_stats: dict[str, dict] = {}
    for strategy in strategies:
        t = time.perf_counter()
        chunks = build_chunks(strategy, pages)
        vectors = embedder.embed_documents([c.text for c in chunks])
        store.upsert(strategy, chunks, vectors)
        stored = store.count(strategy)
        strategy_stats[strategy] = {
            "chunks_built": len(chunks),
            "chunks_stored": stored,
            "avg_chars": sum(len(c.text) for c in chunks) // max(len(chunks), 1),
            "embed_seconds": round(time.perf_counter() - t, 1),
            "applies_query_filter": uses_filter[strategy],
        }
        print(f"[store] {strategy}: {len(chunks)} chunks -> {stored} stored "
              f"({strategy_stats[strategy]['embed_seconds']}s)")

    # 4. benchmark retrieval --------------------------------------------------
    questions = load_benchmark(args.benchmark, args.allow_small_benchmark)
    trace_files: dict[str, object] = {}
    all_traces: list[dict] = []
    for strategy in strategies:
        t = time.perf_counter()
        traces = []
        for q in questions:
            qvec = embedder.embed_query(q["question"])
            filters = q.get("filter") if uses_filter[strategy] else None
            hits = store.search(strategy, qvec, TOP_K, filters)
            traces.append(evaluate_query(q, hits))
        all_traces.extend(traces)
        out = RESULTS / f"traces_{strategy}.jsonl"
        with out.open("w", encoding="utf-8", newline="\n") as fout:
            for trace in traces:
                fout.write(json.dumps(trace, ensure_ascii=False) + "\n")
        trace_files[strategy] = str(out.relative_to(BASE))
        print(f"[search] {strategy}: {len(traces)} queries "
              f"({round(time.perf_counter() - t, 1)}s) -> {out.name}")

    # 5. summary + run manifest ----------------------------------------------
    summary = summarize(all_traces)
    run_manifest = {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {
            "pages_loaded": len(pages),
            "content_pages": len(content_pages),
            "source": str(args.pages),
            "documents": sorted({p.document_id for p in pages}),
        },
        "embedding": {
            "model": embedder.model_name,
            "dimensions": embedder.dimensions,
            "provider": "local (sentence-transformers), cost 0 USD",
        },
        "store": {"backend": "postgresql+pgvector", "table": store.table},
        "strategies": {
            "params": {
                "A_fixed": f"size={FIXED_SIZE},overlap={FIXED_OVERLAP}",
                "B_para": f"max_size={PARA_MAX}",
                "C_para_flt": f"max_size={PARA_MAX} + metadata filter",
            },
            "stats": strategy_stats,
            "trace_files": trace_files,
        },
        "benchmark": {"path": str(args.benchmark), "questions": len(questions)},
        "top_k": TOP_K,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "summary.json").write_text(
        json.dumps({"metrics": summary, "run": run_manifest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n=== Hit@1 / Evidence Hit@3 (per strategy, per split) ===")
    for key, bucket in summary["by_strategy_split"].items():
        f1 = bucket["hit_at_1"]
        f3 = bucket["evidence_hit_at_3"]
        fc = bucket["filter_compliance"]
        print(f"{key:24s} n={f1['n']:3d}  Hit@1={f1['hits']}/{f1['n']}={f1['rate']}  "
              f"EvHit@3={f3['hits']}/{f3['n']}={f3['rate']}  "
              f"filter={fc if fc is not None else '-'}")
    print(f"\nFull metrics + run info: results/summary.json")

    store.close()


if __name__ == "__main__":
    main()
