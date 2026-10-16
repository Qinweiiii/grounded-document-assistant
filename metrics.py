"""Shared behaviour checks and aggregate metrics for both assistant versions."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from common import Passage, Result, by_id


def _contains_missing_term(result: Result, term: str) -> bool:
    lowered = term.lower()
    if any(lowered in item.lower() for item in result["disclosed_missing"]):
        return True
    return lowered in result["rendered"].lower()


def _ordered_subset(expected: list[str], actual: list[str]) -> bool:
    positions = [actual.index(item) for item in expected if item in actual]
    return len(positions) == len(expected) and positions == sorted(positions)


def _faithfulness_problems(result: Result, passages: list[Passage]) -> list[str]:
    lookup = by_id(passages)
    problems: list[str] = []
    source_lines = [line[2:] for line in result["rendered"].splitlines() if line.startswith("> ")]
    corpus_texts = {passage["text"] for passage in passages}
    for source_line in source_lines:
        if source_line not in corpus_texts:
            problems.append("rendered quote is not an exact corpus passage")
    for passage_id in result["supporting_ids"]:
        passage = lookup.get(passage_id)
        if passage is None:
            problems.append(f"unknown supporting id: {passage_id}")
        elif passage["text"] not in source_lines:
            problems.append(f"supporting passage not quoted in full: {passage_id}")
    return problems


def check_case(
    case: dict[str, Any],
    result: Result,
    version: str,
    passages: list[Passage],
) -> list[str]:
    """Return behaviour-level problems; an empty list means the case passes."""
    problems: list[str] = []
    decision = result["decision"]
    if version == "v1":
        expected = case["v1_expected_decision"]
        if decision != expected:
            problems.append(f"decision={decision}, expected={expected}")
    elif decision not in case["v2_acceptable_decisions"]:
        problems.append(
            f"decision={decision}, expected one of {case['v2_acceptable_decisions']}"
        )

    supporting = result["supporting_ids"]
    must_cite = case.get("must_cite", [])
    missing_citations = [item for item in must_cite if item not in supporting]
    if missing_citations:
        problems.append("missing citations: " + ", ".join(missing_citations))
    forbidden_citations = [
        item for item in case.get("must_not_cite", []) if item in supporting
    ]
    if forbidden_citations:
        problems.append("forbidden citations: " + ", ".join(forbidden_citations))
    if decision == "conflict" and must_cite and not _ordered_subset(must_cite, supporting):
        problems.append("conflict citations are not in required order")

    for term in case.get("must_disclose_missing", []):
        if not _contains_missing_term(result, term):
            problems.append(f"missing topic not disclosed: {term}")

    rendered_lower = result["rendered"].lower()
    for required in case.get("require_text", []):
        if required.lower() not in rendered_lower:
            problems.append(f"required text absent: {required}")
    for forbidden in case.get("forbid_text", []):
        if forbidden.lower() in rendered_lower:
            problems.append(f"forbidden text present: {forbidden}")

    if version == "v2":
        for pattern in case.get("must_not_claim_regex", []):
            if any(re.search(pattern, claim) for claim in result["generated_text"]):
                problems.append(f"generated claim matches forbidden regex: {pattern}")

    if result["sensitive"] != case["sensitive_expected"]:
        problems.append(
            f"sensitive={result['sensitive']}, expected={case['sensitive_expected']}"
        )
    problems.extend(_faithfulness_problems(result, passages))
    return problems


def compute_metrics(
    cases: list[dict[str, Any]],
    results: dict[str, Result],
    checks: dict[str, list[str]],
    version: str,
) -> dict[str, Any]:
    total = len(cases)
    passed = sum(not checks[case["id"]] for case in cases)

    unsupported_cases = [
        case for case in cases if case["v1_expected_decision"] == "abstain"
    ]
    unsupported_answers = sum(
        results[case["id"]]["decision"] in {"answer", "conflict"}
        and bool(results[case["id"]]["supporting_ids"])
        for case in unsupported_cases
    )
    supported_cases = [
        case for case in cases if case["v1_expected_decision"] != "abstain"
    ]
    over_abstains = sum(
        results[case["id"]]["decision"] == "abstain" for case in supported_cases
    )

    true_positive = 0
    predicted = 0
    expected = 0
    for case in cases:
        actual_ids = results[case["id"]]["supporting_ids"]
        expected_ids = case.get("must_cite", [])
        predicted += len(actual_ids)
        expected += len(expected_ids)
        true_positive += len(set(actual_ids) & set(expected_ids))

    sensitive_correct = sum(
        results[case["id"]]["sensitive"] == case["sensitive_expected"]
        and (
            not case["sensitive_expected"]
            or "confirm with the document owner" in results[case["id"]]["rendered"]
        )
        for case in cases
    )
    known_limitation_passes = [
        case["id"]
        for case in cases
        if case.get("v1_known_limitation") and not checks[case["id"]]
    ]
    fallbacks = sum(bool(results[case["id"]]["fallback_reason"]) for case in cases)
    forbidden_claim_violations = sum(
        any(
            re.search(pattern, claim)
            for pattern in case.get("must_not_claim_regex", [])
            for claim in results[case["id"]]["generated_text"]
        )
        for case in cases
    )
    return {
        "cases": total,
        "passes": passed,
        "unsupported_answer_rate": unsupported_answers / len(unsupported_cases)
        if unsupported_cases
        else 0.0,
        "over_abstain_rate": over_abstains / len(supported_cases)
        if supported_cases
        else 0.0,
        "citation_precision": true_positive / predicted if predicted else 1.0,
        "citation_recall": true_positive / expected if expected else 1.0,
        "sensitive_notice_correct": sensitive_correct,
        "known_limitation_passes": known_limitation_passes,
        "fallback_rate": fallbacks / total if total else 0.0,
        "must_not_claim_regex_violations": forbidden_claim_violations,
        "failed_validator_counts": Counter(),
        "version": version,
    }
