"""Evaluate retrieved evidence and preserve per-query traces.

Metric definitions follow GUIDE.md:
- A "hit" is a top chunk that belongs to the gold source/page AND contains the
  recorded evidence quote (or a documented alternative).
- Hit@1  = questions whose rank-1 chunk is a hit / total questions.
- Evidence Hit@3 = questions with at least one hit in the top-3 / total.

Evidence matching is automated text comparison only; manual labels (grounding
quality, chunk coherence) are NOT inferred here — traces carry everything a
human grader needs to score them separately.
"""
import re
import unicodedata
from typing import Any

TOP_K = 3  # Evidence Hit@3 window

# Chars PDF extraction may turn quotes into; ignored when comparing evidence.
_PUNCT_RE = re.compile(r"[\"'“”‘’«»„‟\u00ad\u200b\u200c\u200d\ufeff]")


def _normalize(text: str) -> str:
    """NFC, casefold, punctuation-agnostic, whitespace-collapsed form."""
    text = unicodedata.normalize("NFC", text).casefold()
    text = _PUNCT_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _squash(text: str) -> str:
    """Like _normalize but with all whitespace removed.

    Handles evidence quotes whose line breaks do not survive chunking (PDF
    columns, hard-wrapped paragraphs) without inventing content.
    """
    return re.sub(r"\s+", "", _normalize(text))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _evidence_found(chunk_text: str, evidence: Any) -> bool:
    """True if any documented evidence quote appears in the chunk text."""
    quotes = _as_list(evidence)
    if not quotes:
        return False
    squashed_chunk = _squash(chunk_text)
    return any(_squash(str(quote)) and _squash(str(quote)) in squashed_chunk for quote in quotes)


def _page_matches(hit: dict[str, Any], gold_page: Any) -> bool:
    """Gold page equals the chunk page, or falls inside a multi-page chunk."""
    pages = _as_list(gold_page)
    if not pages:
        return True  # no gold page recorded: source + evidence decide the hit
    page = hit.get("page")
    metadata = hit.get("metadata") or {}
    page_start, page_end = metadata.get("page_start"), metadata.get("page_end")
    for gold in pages:
        if page == gold:
            return True
        if isinstance(page_start, int) and isinstance(page_end, int) and page_start <= gold <= page_end:
            return True
    return False


def _source_matches(hit: dict[str, Any], gold_source: Any) -> bool:
    """Gold document id equals chunk document, or the source path carries it."""
    sources = _as_list(gold_source)
    if not sources:
        return True
    chunk_id = str(hit.get("chunk_id", ""))
    for gold in sources:
        gold = str(gold)
        if (
            hit.get("document_id") == gold
            or hit.get("source", "").endswith(gold)
            or chunk_id.startswith(gold + "#")
            or chunk_id.startswith(gold)
        ):
            return True
    return False


def _filter_ok(hit: dict[str, Any], filters: dict[str, Any] | None) -> bool | None:
    """Whether a hit's metadata satisfies the question's filter.

    None when the question has no filter. Values compare loosely as strings so
    jsonb int 10 matches filter value "10" (type noise, not a real mismatch).
    """
    if not filters:
        return None
    metadata = hit.get("metadata") or {}
    return all(
        key in metadata and str(metadata[key]) == str(value) for key, value in filters.items()
    )


def _is_hit(hit: dict[str, Any], question: dict[str, Any]) -> bool:
    """GUIDE.md hit rule: gold source + gold page + enough evidence."""
    return (
        _source_matches(hit, question.get("gold_source_id"))
        and _page_matches(hit, question.get("gold_page"))
        and _evidence_found(hit.get("text", ""), question.get("evidence_quote"))
    )


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Score one question's top-k hits; return a trace for manual review."""
    filters = question.get("filter") or None
    ranked = hits[:TOP_K]
    hit_flags = [_is_hit(hit, question) for hit in ranked]
    filter_flags = [_filter_ok(hit, filters) for hit in ranked]

    strategy = "unknown"
    for hit in ranked:
        strategy = (hit.get("metadata") or {}).get("strategy") or hit.get("strategy") or strategy
        if strategy != "unknown":
            break

    trace = {
        "question_id": question.get("id"),
        "split": question.get("split"),
        "question": question.get("question"),
        "strategy": strategy,
        "hit_at_1": bool(hit_flags and hit_flags[0]),
        "evidence_hit_at_3": any(hit_flags),  # at least one hit inside top-3
        "num_hits": sum(hit_flags),
        "top_k": len(ranked),
        "filter_compliance": (
            round(sum(1 for f in filter_flags if f) / len(filter_flags), 4)
            if filters
            else None
        ),
        "gold": {
            "gold_source_id": question.get("gold_source_id"),
            "gold_page": question.get("gold_page"),
            "evidence_quote": question.get("evidence_quote"),
        },
        "expected_answer": question.get("expected_answer"),
        "hits_trace": [
            {
                "rank": rank,
                "chunk_id": hit.get("chunk_id"),
                "score": round(float(hit.get("score", 0.0)), 6),
                "source": hit.get("source"),
                "page": hit.get("page"),
                "hit": is_hit,
                "evidence_found": _evidence_found(hit.get("text", ""), question.get("evidence_quote")),
                "filter_ok": filter_ok,
                "text": hit.get("text", ""),
            }
            for rank, (hit, is_hit, filter_ok) in enumerate(zip(ranked, hit_flags, filter_flags), start=1)
        ],
    }
    return trace


def _rate(traces: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Numerator/denominator and rate for a boolean trace key."""
    n = len(traces)
    hits = sum(1 for t in traces if t.get(key))
    return {"n": n, "hits": hits, "rate": round(hits / n, 4) if n else None}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and split.

    Returns per (strategy, split), per strategy, and overall numbers with
    numerator/denominator (rates alone are not acceptable per GUIDE.md).
    Filter compliance covers filtered questions only.
    """
    def bucket(group: list[dict[str, Any]]) -> dict[str, Any]:
        filtered = [t for t in group if any(h.get("filter_ok") is not None for h in t["hits_trace"])]
        compliance = (
            round(
                sum(t["filter_compliance"] for t in filtered if t["filter_compliance"] is not None)
                / len(filtered),
                4,
            )
            if filtered
            else None
        )
        return {
            "hit_at_1": _rate(group, "hit_at_1"),
            "evidence_hit_at_3": _rate(group, "evidence_hit_at_3"),
            "filter_compliance": compliance,
            "questions": len(group),
        }

    by_strategy_split: dict[str, dict[str, Any]] = {}
    for trace in traces:
        key = f"{trace.get('strategy', 'unknown')}/{trace.get('split', 'unknown')}"
        by_strategy_split.setdefault(key, []).append(trace)
    strategy_split = {key: bucket(group) for key, group in sorted(by_strategy_split.items())}

    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        by_strategy.setdefault(trace.get("strategy", "unknown"), []).append(trace)
    strategy = {key: bucket(group) for key, group in sorted(by_strategy.items())}

    by_split: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        by_split.setdefault(trace.get("split", "unknown"), []).append(trace)
    split = {key: bucket(group) for key, group in sorted(by_split.items())}

    return {
        "overall": bucket(traces),
        "by_strategy": strategy,
        "by_split": split,
        "by_strategy_split": strategy_split,
    }
