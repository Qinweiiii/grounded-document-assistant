"""Shared data structures, loaders, ordering, and rendering helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS_PATH = ROOT / "corpus.json"
DEFAULT_CASES_PATH = ROOT / "eval_cases.json"


class Passage(TypedDict):
    id: str
    doc_id: str
    doc_title: str
    date: str | None
    text: str


class Result(TypedDict):
    decision: str
    supporting_ids: list[str]
    related_ids: list[str]
    disclosed_missing: list[str]
    generated_text: list[str]
    rendered: str
    sensitive: bool
    flagged_injection_ids: list[str]
    fallback_reason: str | None


def _load_json_list(path: str | Path) -> list[dict[str, Any]]:
    resolved = Path(path)
    with resolved.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {resolved}")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError(f"Expected every item in {resolved} to be an object")
    return data


def load_corpus(path: str | Path = DEFAULT_CORPUS_PATH) -> list[Passage]:
    raw = _load_json_list(path)
    required = {"id", "doc_id", "doc_title", "date", "text"}
    passages: list[Passage] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Corpus item {index} is missing: {sorted(missing)}")
        passage_id = item["id"]
        if not isinstance(passage_id, str) or passage_id in seen:
            raise ValueError(f"Corpus item {index} has an invalid or duplicate id")
        if item["date"] is not None and not isinstance(item["date"], str):
            raise ValueError(f"Corpus item {passage_id} has an invalid date")
        for field in ("doc_id", "doc_title", "text"):
            if not isinstance(item[field], str):
                raise ValueError(f"Corpus item {passage_id} has an invalid {field}")
        seen.add(passage_id)
        passages.append(
            {
                "id": passage_id,
                "doc_id": item["doc_id"],
                "doc_title": item["doc_title"],
                "date": item["date"],
                "text": item["text"],
            }
        )
    return passages


def load_cases(path: str | Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    return _load_json_list(path)


def by_id(passages: list[Passage]) -> dict[str, Passage]:
    return {passage["id"]: passage for passage in passages}


def date_order(passages: list[Passage]) -> list[Passage]:
    """Sort dated passages newest first, retaining corpus order for undated ones."""
    dated = sorted(
        (passage for passage in passages if passage["date"]),
        key=lambda passage: passage["date"] or "",
        reverse=True,
    )
    return dated + [passage for passage in passages if not passage["date"]]


def source_label(passage: Passage) -> str:
    date = passage["date"] or "no recorded date"
    return (
        f'{passage["doc_title"]} ({passage["doc_id"]}) '
        f'· entry {passage["id"]} · {date}'
    )


def full_quote(passage: Passage) -> str:
    """Render a full passage in a machine-checkable Markdown quote block."""
    return f'{source_label(passage)}\n> {passage["text"]}'
