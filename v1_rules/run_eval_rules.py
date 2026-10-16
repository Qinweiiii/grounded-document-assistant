"""Run the deterministic v1 evaluation and write a Markdown report."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common import DEFAULT_CASES_PATH, ROOT, load_cases, load_corpus
from metrics import check_case, compute_metrics
from v1_rules.assistant_rules import answer


DEFAULT_RESULTS_PATH = Path(__file__).resolve().parent / "results_rules.md"


def regression_problems(
    cases: list[dict[str, Any]], results: dict[str, dict[str, Any]]
) -> list[str]:
    problems: list[str] = []
    for case in cases:
        actual = case.get("v1_actual")
        if actual is None:
            continue
        result = results[case["id"]]
        if result["decision"] != actual["decision"]:
            problems.append(
                f"{case['id']}: decision {result['decision']} != {actual['decision']}"
            )
        if result["supporting_ids"] != actual["cites"]:
            problems.append(
                f"{case['id']}: citations {result['supporting_ids']} != {actual['cites']}"
            )
    return problems


def _rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def make_report(
    cases: list[dict[str, Any]],
    results: dict[str, dict[str, Any]],
    checks: dict[str, list[str]],
    metrics: dict[str, Any],
) -> str:
    lines = [
        "# v1 rules evaluation",
        "",
        "| Case | Category | Decision | Supporting passages | Reference regression | Behaviour | Problems |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in cases:
        result = results[case["id"]]
        problems = checks[case["id"]]
        reference = case.get("v1_actual")
        reference_match = (
            reference is not None
            and result["decision"] == reference["decision"]
            and result["supporting_ids"] == reference["cites"]
        )
        lines.append(
            "| {id} | {category} | {decision} | {citations} | {regression} | {status} | {problems} |".format(
                id=case["id"],
                category=case.get("category", ""),
                decision=result["decision"],
                citations=", ".join(result["supporting_ids"]) or "—",
                regression="MATCH" if reference_match else ("MISMATCH" if reference else "N/A"),
                status="PASS" if not problems else "FAIL",
                problems="; ".join(problems).replace("|", "\\|") or "—",
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate metrics",
            "",
            f"- Passes: {metrics['passes']}/{metrics['cases']}",
            f"- Unsupported-answer rate: {_rate(metrics['unsupported_answer_rate'])}",
            f"- Over-abstain rate: {_rate(metrics['over_abstain_rate'])}",
            f"- Citation precision: {_rate(metrics['citation_precision'])}",
            f"- Citation recall: {_rate(metrics['citation_recall'])}",
            (
                "- Sensitive notice correctness: "
                f"{metrics['sensitive_notice_correct']}/{metrics['cases']}"
            ),
            (
                "- Known-limitation cases that nevertheless passed: "
                + str(len(metrics["known_limitation_passes"]))
                + " ("
                + (", ".join(metrics["known_limitation_passes"]) or "none")
                + ")"
            ),
            "",
            "## Regression check",
            "",
            "All cases with `v1_actual` matched the reference decision and citation order.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--output", default=str(DEFAULT_RESULTS_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    passages = load_corpus()
    cases = load_cases(args.cases)
    results = {case["id"]: answer(case["question"], passages) for case in cases}

    # The supplied cases are the regression oracle. Optional held-out files may
    # omit v1_actual and are evaluated without inventing a regression target.
    regression = regression_problems(cases, results)
    if regression:
        detail = "\n".join(f"- {problem}" for problem in regression)
        raise SystemExit("v1 regression mismatch:\n" + detail)

    checks = {
        case["id"]: check_case(case, results[case["id"]], "v1", passages)
        for case in cases
    }
    aggregate = compute_metrics(cases, results, checks, "v1")
    report = make_report(cases, results, checks, aggregate)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
