"""Run v2 in offline replay mode by default, or explicitly in live mode."""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common import DEFAULT_CASES_PATH, ROOT, by_id, load_cases, load_corpus
from metrics import check_case, compute_metrics
from v2_llm.assistant_llm import GroundedLLMAssistant
from v2_llm.config import (
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TIMEOUT_SECONDS,
)
from v2_llm.llm_client import (
    OpenAICompatibleClient,
    RecordingClient,
    ReplayClient,
    cache_key,
)
from v2_llm.prompts import PROMPT_VERSION


V2_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = V2_DIR / "recorded_outputs"
DEFAULT_RESULTS_PATH = V2_DIR / "results_llm.md"
DEFAULT_REVIEW_PATH = V2_DIR / "human_review.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--replay", action="store_true")
    parser.add_argument("--full-corpus", action="store_true")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument(
        "--case-ids",
        help="Comma-separated case IDs to run, for targeted retries.",
    )
    parser.add_argument("--output", default=str(DEFAULT_RESULTS_PATH))
    parser.add_argument("--human-review", default=str(DEFAULT_REVIEW_PATH))
    return parser.parse_args()


def client_for_case(
    args: argparse.Namespace,
    question: str,
    candidate_ids: list[str],
):
    model = os.getenv("LLM_MODEL", LLM_MODEL)
    key = cache_key(PROMPT_VERSION, model, question, candidate_ids)
    recording_path = RECORDINGS_DIR / f"{key}.json"
    if not args.live:
        return ReplayClient(recording_path), None
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        return None, "no_api_key"
    if not model:
        return None, "no_model"
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER)
    if provider != "openai-compatible":
        return None, "unsupported_provider"
    base_url = os.getenv(
        "LLM_BASE_URL",
        LLM_BASE_URL,
    )
    live = OpenAICompatibleClient(
        api_key,
        model,
        base_url,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
    )
    return (
        RecordingClient(
            live,
            recording_path,
            model,
            PROMPT_VERSION,
            candidate_ids,
        ),
        None,
    )


def _write_human_review(
    path: Path,
    traces: dict[str, dict[str, Any] | None],
    passages,
) -> None:
    lookup = by_id(passages)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["case_id", "claim", "quote", "passage_text", "meaning_drift", "notes"]
        )
        for case_id, trace in traces.items():
            if trace is None:
                continue
            for claim in trace["claims"]:
                quotes = "\n---\n".join(
                    evidence["quote"] for evidence in claim["evidence"]
                )
                passage_texts = "\n---\n".join(
                    lookup[evidence["id"]]["text"]
                    for evidence in claim["evidence"]
                )
                writer.writerow(
                    [case_id, claim["text"], quotes, passage_texts, "", ""]
                )


def _rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def make_report(cases, results, checks, aggregate, validator_failures, traces) -> str:
    lines = [
        "# v2 LLM evaluation",
        "",
        "| Case | Category | Decision | Supporting passages | Fallback | Behaviour | Problems |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in cases:
        result = results[case["id"]]
        problems = checks[case["id"]]
        lines.append(
            "| {id} | {category} | {decision} | {citations} | {fallback} | {status} | {problems} |".format(
                id=case["id"],
                category=case.get("category", ""),
                decision=result["decision"],
                citations=", ".join(result["supporting_ids"]) or "—",
                fallback=result["fallback_reason"] or "—",
                status="PASS" if not problems else "FAIL",
                problems="; ".join(problems).replace("|", "\\|") or "—",
            )
        )
    answer_case_ids = [
        case_id
        for case_id, result in results.items()
        if result["decision"] in {"answer", "conflict"}
    ]
    claim_count = sum(
        len(traces[case_id]["claims"])
        for case_id in answer_case_ids
        if traces[case_id] is not None
    )
    claims_per_answer = claim_count / len(answer_case_ids) if answer_case_ids else 0.0
    validator_summary = ", ".join(
        f"{name}={count}" for name, count in sorted(validator_failures.items())
    ) or "none"
    number_violations = validator_failures.get(
        "validator_4_number_not_in_evidence", 0
    )
    lines.extend(
        [
            "",
            "## Aggregate metrics",
            "",
            f"- Passes: {aggregate['passes']}/{aggregate['cases']}",
            f"- Unsupported-answer rate: {_rate(aggregate['unsupported_answer_rate'])}",
            f"- Over-abstain rate: {_rate(aggregate['over_abstain_rate'])}",
            f"- Citation precision: {_rate(aggregate['citation_precision'])}",
            f"- Citation recall: {_rate(aggregate['citation_recall'])}",
            (
                "- Sensitive notice correctness: "
                f"{aggregate['sensitive_notice_correct']}/{aggregate['cases']}"
            ),
            f"- Fallback rate: {_rate(aggregate['fallback_rate'])}",
            f"- Claims per answer: {claims_per_answer:.2f}",
            f"- Number-fidelity violations: {number_violations}",
            (
                "- `must_not_claim_regex` violations: "
                f"{aggregate['must_not_claim_regex_violations']}"
            ),
            f"- Failed validator counts: {validator_summary}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    passages = load_corpus()
    cases = load_cases(args.cases)
    if args.case_ids:
        requested = {item.strip() for item in args.case_ids.split(",") if item.strip()}
        cases = [case for case in cases if case["id"] in requested]
        found = {case["id"] for case in cases}
        if found != requested:
            missing = ", ".join(sorted(requested - found))
            raise SystemExit(f"Unknown case IDs: {missing}")
    assistant = GroundedLLMAssistant(
        passages, top_k=args.top_k, full_corpus=args.full_corpus
    )
    results = {}
    traces = {}
    for case in cases:
        candidates = assistant.candidates(case["question"])
        client, no_client_reason = client_for_case(
            args,
            case["question"],
            [passage["id"] for passage in candidates],
        )
        result, trace = assistant.run(
            case["question"],
            client,
            no_client_reason or "no_api_key",
        )
        results[case["id"]] = result
        traces[case["id"]] = trace

    checks = {
        case["id"]: check_case(case, results[case["id"]], "v2", passages)
        for case in cases
    }
    aggregate = compute_metrics(cases, results, checks, "v2")
    report = make_report(
        cases,
        results,
        checks,
        aggregate,
        assistant.validator_failures,
        traces,
    )
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    review_path = Path(args.human_review)
    if not review_path.is_absolute():
        review_path = ROOT / review_path
    _write_human_review(review_path, traces, passages)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
