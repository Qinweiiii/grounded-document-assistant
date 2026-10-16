from __future__ import annotations

import unittest

from common import load_cases, load_corpus
from metrics import check_case
from v1_rules.assistant_rules import answer
from v1_rules.run_eval_rules import regression_problems


class V1RulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.passages = load_corpus()
        cls.cases = load_cases()
        cls.results = {
            case["id"]: answer(case["question"], cls.passages)
            for case in cls.cases
        }

    def test_regression_matches_reference_actuals(self) -> None:
        self.assertEqual([], regression_problems(self.cases, self.results))

    def test_all_supporting_passages_are_quoted_verbatim(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"]):
                problems = check_case(
                    case,
                    self.results[case["id"]],
                    "v1",
                    self.passages,
                )
                faithfulness = [
                    problem
                    for problem in problems
                    if "quote" in problem or "quoted in full" in problem
                ]
                self.assertEqual([], faithfulness)

    def test_conflict_order_is_newest_then_undated(self) -> None:
        result = self.results["T3"]
        self.assertEqual(["IT-01", "IT-03", "IT-04"], result["supporting_ids"])

    def test_injection_is_quoted_and_flagged_not_followed(self) -> None:
        result = self.results["T10"]
        self.assertEqual(["FAQ-02"], result["flagged_injection_ids"])
        self.assertIn("not followed", result["rendered"])
        self.assertEqual([], result["generated_text"])

    def test_money_case_has_fixed_notice(self) -> None:
        result = self.results["X6"]
        self.assertTrue(result["sensitive"])
        self.assertIn("confirm with the document owner", result["rendered"])


if __name__ == "__main__":
    unittest.main()
