"""Rule-based grounded document assistant.

This is a structural port of ``reference_v1_assistant.py``. Retrieval,
thresholds, conflict detection, ordering, and notices intentionally retain the
reference behaviour, including its known limitations.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from common import Passage, Result, by_id, date_order, full_quote, load_corpus


THRESHOLD = 0.6
MAX_SHOWN = 3
SENSITIVE_PREFIXES = (
    "reimburs",
    "expens",
    "salar",
    "bonu",
    "pay",
    "invoic",
    "tax",
    "budget",
    "deadlin",
    "reward",
)
INJECTION_PATTERNS = [
    r"ignore\s+(?:\w+\s+)*instructions",
    r"disregard",
    r"system override",
    r"you are now",
]
STOP = set(
    """the a an of to is are was were what how do does for in on at per by with be can could i me my we our
you your it they there this that and or if as from get give confirm tell say many much just no only please about
who when where which must should may company use""".split()
)

_UNIT = re.compile(r"(\$)?(\d+)(?:\s?([a-z]+))?")


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            if suffix == "s" and word.endswith("ss"):
                return word
            word = word[: -len(suffix)]
            if (
                suffix in ("ing", "ed")
                and len(word) > 3
                and word[-1] == word[-2]
                and word[-1] not in "aeiouslz"
            ):
                word = word[:-1]
            return word
    return word


def toks(text: str) -> set[str]:
    return {
        stem(word)
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOP
    }


def score(query: str, passage: Passage) -> float:
    query_terms = toks(query)
    overlap = query_terms & toks(passage["text"])
    return round(len(overlap) / max(len(query_terms), 1), 6)


def is_injection(passage: Passage) -> bool:
    return any(
        re.search(pattern, passage["text"].lower())
        for pattern in INJECTION_PATTERNS
    )


def is_sensitive(query: str, passages: Iterable[Passage]) -> bool:
    selected = list(passages)
    words = toks(query)
    if selected:
        words = words.union(*(toks(passage["text"]) for passage in selected))
    return any(word.startswith(SENSITIVE_PREFIXES) for word in words)


def signature(text: str) -> dict[str, set[str]]:
    signatures: dict[str, set[str]] = {}
    for currency, number, unit in _UNIT.findall(text.lower()):
        normalized = "$" if currency else (stem(unit) if unit and unit not in STOP else None)
        if normalized:
            signatures.setdefault(normalized, set()).add(number)
    return signatures


def conflicts(left: Passage, right: Passage) -> bool:
    left_signature = signature(left["text"])
    right_signature = signature(right["text"])
    return any(
        unit in right_signature and left_signature[unit] != right_signature[unit]
        for unit in left_signature
    )


def _render(
    decision: str,
    shown: list[Passage],
    related_ids: list[str],
    notice: str,
    flagged_ids: list[str],
) -> str:
    lines = [f"[{decision.upper()}]"]
    for passage in shown:
        lines.append(full_quote(passage))
        if passage["id"] in flagged_ids:
            lines.append(
                "! This passage contains instruction-like text. It is quoted as "
                "document content only and was not followed."
            )
    lines.append(notice)
    if related_ids:
        lines.append("Also matched (not used above): " + ", ".join(related_ids))
    return "\n\n".join(lines)


def answer(query: str, passages: list[Passage] | None = None) -> Result:
    corpus = load_corpus() if passages is None else passages
    scored = [(score(query, passage), index, passage) for index, passage in enumerate(corpus)]
    hits = sorted(
        (hit for hit in scored if hit[0] >= THRESHOLD),
        key=lambda hit: (-hit[0], hit[1]),
    )

    if not hits:
        notice = "No passage in the supplied documents supports an answer. Nothing was guessed."
        return {
            "decision": "abstain",
            "supporting_ids": [],
            "related_ids": [],
            "disclosed_missing": sorted(toks(query)),
            "generated_text": [],
            "rendered": _render("abstain", [], [], notice, []),
            "sensitive": False,
            "flagged_injection_ids": [],
            "fallback_reason": None,
        }

    supported = [passage for _, _, passage in hits]
    clashing = [
        passage
        for passage in supported
        if any(conflicts(passage, other) for other in supported if other is not passage)
    ]
    shown = clashing if clashing else supported[:MAX_SHOWN]
    sensitive = is_sensitive(query, shown)
    confirm = (
        " Money/deadline topic: please confirm with the document owner before acting."
        if sensitive
        else ""
    )

    if clashing:
        shown = date_order(clashing)
        decision = "conflict"
        notice = (
            "These passages say different things. The assistant does not pick one; "
            "listed newest first, undated last." + confirm
        )
    else:
        decision = "answer"
        notice = "Quoted verbatim from the cited passage(s)." + confirm

    covered = set().union(*(toks(passage["text"]) for passage in shown))
    missing = sorted(toks(query) - covered)
    if missing:
        notice += (
            " Question terms not found in the cited passage(s): "
            + ", ".join(missing)
            + "."
        )

    supporting_ids = [passage["id"] for passage in shown]
    used = set(supporting_ids)
    related_ids = [passage["id"] for passage in supported if passage["id"] not in used]
    flagged_ids = [passage["id"] for passage in shown if is_injection(passage)]
    rendered = _render(decision, shown, related_ids, notice, flagged_ids)
    return {
        "decision": decision,
        "supporting_ids": supporting_ids,
        "related_ids": related_ids,
        "disclosed_missing": missing,
        "generated_text": [],
        "rendered": rendered,
        "sensitive": sensitive,
        "flagged_injection_ids": flagged_ids,
        "fallback_reason": None,
    }


def passages_for_result(result: Result, passages: list[Passage]) -> list[Passage]:
    lookup = by_id(passages)
    return [lookup[passage_id] for passage_id in result["supporting_ids"]]


if __name__ == "__main__":
    for sample in (
        "How do I use the VPN?",
        "What is the office system password policy?",
        "Where is the office located?",
    ):
        print(f"Q: {sample}\n{answer(sample)['rendered']}\n")
