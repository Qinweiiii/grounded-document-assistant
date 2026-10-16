"""Deterministic validation boundary for raw LLM output."""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from common import Passage, by_id
from v1_rules.assistant_rules import conflicts, is_injection, toks


RELATIONS = {"answers", "partial", "related_only", "irrelevant"}
WINNER_LANGUAGE = re.compile(
    r"supersede|superseded|takes precedence|overrides|should follow|"
    r"is the correct|is the valid|is current|most up-to-date|"
    r"latest version applies|replaces|outdated and",
    re.IGNORECASE,
)
NUMBER_TOKEN = re.compile(r"\$\d+(?:\.\d+)?|\d{1,2}:\d{2}|\d+(?:st|nd|rd|th)?", re.IGNORECASE)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def parse_schema(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, "validator_1_schema"
    if not isinstance(data, dict):
        return None, "validator_1_schema"
    required = {"passage_assessment", "claims", "not_covered", "semantic_conflicts"}
    if not required.issubset(data):
        return None, "validator_1_schema"
    assessments = data["passage_assessment"]
    claims = data["claims"]
    conflicts_data = data["semantic_conflicts"]
    if not isinstance(assessments, list) or not isinstance(claims, list):
        return None, "validator_1_schema"
    if not _is_string_list(data["not_covered"]) or not isinstance(conflicts_data, list):
        return None, "validator_1_schema"
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("id"), str)
        or item.get("relation") not in RELATIONS
        for item in assessments
    ):
        return None, "validator_1_schema"
    for claim in claims:
        if (
            not isinstance(claim, dict)
            or not isinstance(claim.get("text"), str)
            or not isinstance(claim.get("evidence"), list)
            or not claim["evidence"]
        ):
            return None, "validator_1_schema"
        if any(
            not isinstance(evidence, dict)
            or not isinstance(evidence.get("id"), str)
            or not isinstance(evidence.get("quote"), str)
            for evidence in claim["evidence"]
        ):
            return None, "validator_1_schema"
    if any(
        not isinstance(item, dict)
        or not _is_string_list(item.get("ids"))
        or not isinstance(item.get("description"), str)
        for item in conflicts_data
    ):
        return None, "validator_1_schema"
    # Unknown keys are intentionally ignored. Copy only the shared schema.
    return {key: data[key] for key in required}, None


def validate_evidence_ids(
    data: dict[str, Any], candidates: list[Passage], corpus: list[Passage]
) -> str | None:
    corpus_ids = set(by_id(corpus))
    candidate_ids = {passage["id"] for passage in candidates}
    referenced = [
        evidence["id"]
        for claim in data["claims"]
        for evidence in claim["evidence"]
    ]
    referenced.extend(
        passage_id
        for conflict in data["semantic_conflicts"]
        for passage_id in conflict["ids"]
    )
    if any(item not in corpus_ids or item not in candidate_ids for item in referenced):
        return "validator_2_invalid_evidence_id"
    return None


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def validate_exact_quotes(data: dict[str, Any], corpus: list[Passage]) -> str | None:
    lookup = by_id(corpus)
    for claim in data["claims"]:
        for evidence in claim["evidence"]:
            passage = lookup.get(evidence["id"])
            if passage is None or _normalize_whitespace(evidence["quote"]) not in _normalize_whitespace(
                passage["text"]
            ):
                return "validator_3_quote_not_verbatim"
    return None


def validate_number_fidelity(data: dict[str, Any]) -> str | None:
    for claim in data["claims"]:
        evidence_numbers = {
            token.lower()
            for evidence in claim["evidence"]
            for token in NUMBER_TOKEN.findall(evidence["quote"])
        }
        claim_numbers = {token.lower() for token in NUMBER_TOKEN.findall(claim["text"])}
        if not claim_numbers.issubset(evidence_numbers):
            return "validator_4_number_not_in_evidence"
    return None


def validate_claim_relations(data: dict[str, Any]) -> str | None:
    relations = {item["id"]: item["relation"] for item in data["passage_assessment"]}
    if any(
        relations.get(evidence["id"]) not in {"answers", "partial"}
        for claim in data["claims"]
        for evidence in claim["evidence"]
    ):
        return "validator_5_claim_uses_non_supporting_relation"
    return None


def validate_no_winner_language(data: dict[str, Any]) -> str | None:
    generated = [claim["text"] for claim in data["claims"]]
    generated.extend(item["description"] for item in data["semantic_conflicts"])
    if any(WINNER_LANGUAGE.search(text) for text in generated):
        return "validator_6_winner_picking_language"
    return None


def question_terms_missing_from_claims(
    question: str, data: dict[str, Any], corpus: list[Passage]
) -> set[str]:
    lookup = by_id(corpus)
    cited_ids = {
        evidence["id"]
        for claim in data["claims"]
        for evidence in claim["evidence"]
    }
    if not cited_ids:
        cited_ids = {
            item["id"]
            for item in data["passage_assessment"]
            if item["relation"] == "related_only" and item["id"] in lookup
        }
    covered: set[str] = set()
    for passage_id in cited_ids:
        if passage_id in lookup:
            covered.update(toks(lookup[passage_id]["text"]))
    return toks(question) - covered


def validate_missing_disclosure(
    question: str,
    data: dict[str, Any],
    corpus: list[Passage],
    code_disclosed_missing: set[str] | None = None,
) -> str | None:
    missing = question_terms_missing_from_claims(question, data, corpus)
    disclosed = toks(" ".join(data["not_covered"]))
    disclosed.update(code_disclosed_missing or set())
    if not missing.issubset(disclosed):
        return "validator_7_missing_not_covered"
    return None


def validate_numeric_conflict_completeness(
    data: dict[str, Any], candidates: list[Passage]
) -> str | None:
    relations = {item["id"]: item["relation"] for item in data["passage_assessment"]}
    direct = [
        passage
        for passage in candidates
        if relations.get(passage["id"]) in {"answers", "partial"}
    ]
    conflict_ids = {
        passage["id"]
        for passage in direct
        if any(conflicts(passage, other) for other in direct if other is not passage)
    }
    evidence_ids = {
        evidence["id"]
        for claim in data["claims"]
        for evidence in claim["evidence"]
    }
    if not conflict_ids.issubset(evidence_ids):
        return "validator_8_incomplete_numeric_conflict"
    return None


def validate_no_injection_artifact(
    data: dict[str, Any], candidates: list[Passage]
) -> str | None:
    if not any(is_injection(passage) for passage in candidates):
        return None
    generated = [claim["text"] for claim in data["claims"]]
    generated.extend(data["not_covered"])
    generated.extend(item["description"] for item in data["semantic_conflicts"])
    if any("system override success" in text.lower() for text in generated):
        return "validator_9_injection_artifact"
    return None


def validate_response(
    raw: str,
    question: str,
    candidates: list[Passage],
    corpus: list[Passage],
    failure_counts: Counter[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    data, reason = parse_schema(raw)
    if reason:
        if failure_counts is not None:
            failure_counts[reason] += 1
        return None, reason
    assert data is not None
    code_disclosed_missing = question_terms_missing_from_claims(question, data, corpus)
    checks = (
        lambda: validate_evidence_ids(data, candidates, corpus),
        lambda: validate_exact_quotes(data, corpus),
        lambda: validate_number_fidelity(data),
        lambda: validate_claim_relations(data),
        lambda: validate_no_winner_language(data),
        lambda: validate_missing_disclosure(
            question,
            data,
            corpus,
            code_disclosed_missing,
        ),
        lambda: validate_numeric_conflict_completeness(data, candidates),
        lambda: validate_no_injection_artifact(data, candidates),
    )
    for check in checks:
        reason = check()
        if reason:
            if failure_counts is not None:
                failure_counts[reason] += 1
            return None, reason
    return data, None
