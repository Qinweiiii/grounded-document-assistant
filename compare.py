"""Compare v1 and v2 behaviour on the same cases."""
from __future__ import annotations

import argparse
from pathlib import Path

from common import DEFAULT_CASES_PATH, load_cases, load_corpus
from metrics import check_case, compute_metrics
from v1_rules.assistant_rules import answer as v1_answer
from v2_llm.assistant_llm import GroundedLLMAssistant
from v2_llm.run_eval_llm import client_for_case


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--replay", action="store_true")
    parser.add_argument("--full-corpus", action="store_true")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    return parser.parse_args()


def _rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def build_comparison(args: argparse.Namespace) -> str:
    passages = load_corpus()
    cases = load_cases(args.cases)
    assistant = GroundedLLMAssistant(
        passages,
        top_k=args.top_k,
        full_corpus=args.full_corpus,
    )
    v1_results = {}
    v2_results = {}
    for case in cases:
        question = case["question"]
        v1_results[case["id"]] = v1_answer(question, passages)
        candidates = assistant.candidates(question)
        client, no_client_reason = client_for_case(
            args,
            question,
            [passage["id"] for passage in candidates],
        )
        v2_results[case["id"]] = assistant.answer(
            question,
            client,
            no_client_reason or "no_api_key",
        )

    v1_checks = {
        case["id"]: check_case(case, v1_results[case["id"]], "v1", passages)
        for case in cases
    }
    v2_checks = {
        case["id"]: check_case(case, v2_results[case["id"]], "v2", passages)
        for case in cases
    }
    v1_metrics = compute_metrics(cases, v1_results, v1_checks, "v1")
    v2_metrics = compute_metrics(cases, v2_results, v2_checks, "v2")

    lines = [
        "# v1 vs v2 comparison",
        "",
        "| Case | v1 | v2 | v1 decision | v2 decision | v2 fallback |",
        "|---|---|---|---|---|---|",
    ]
    for case in cases:
        case_id = case["id"]
        lines.append(
            "| {case_id} | {v1_status} | {v2_status} | {v1_decision} | {v2_decision} | {fallback} |".format(
                case_id=case_id,
                v1_status="PASS" if not v1_checks[case_id] else "FAIL",
                v2_status="PASS" if not v2_checks[case_id] else "FAIL",
                v1_decision=v1_results[case_id]["decision"],
                v2_decision=v2_results[case_id]["decision"],
                fallback=v2_results[case_id]["fallback_reason"] or "—",
            )
        )

    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "| Metric | v1 | v2 |",
            "|---|---:|---:|",
            f"| Passes | {v1_metrics['passes']}/{v1_metrics['cases']} | {v2_metrics['passes']}/{v2_metrics['cases']} |",
            f"| Unsupported-answer rate | {_rate(v1_metrics['unsupported_answer_rate'])} | {_rate(v2_metrics['unsupported_answer_rate'])} |",
            f"| Over-abstain rate | {_rate(v1_metrics['over_abstain_rate'])} | {_rate(v2_metrics['over_abstain_rate'])} |",
            f"| Citation precision | {_rate(v1_metrics['citation_precision'])} | {_rate(v2_metrics['citation_precision'])} |",
            f"| Citation recall | {_rate(v1_metrics['citation_recall'])} | {_rate(v2_metrics['citation_recall'])} |",
            f"| Fallback rate | — | {_rate(v2_metrics['fallback_rate'])} |",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    print(build_comparison(parse_args()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
