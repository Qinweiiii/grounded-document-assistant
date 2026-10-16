from __future__ import annotations

import argparse
import unittest

from compare import build_comparison
from common import load_cases


class CompareTests(unittest.TestCase):
    def test_replay_comparison_has_every_case_and_aggregate(self) -> None:
        args = argparse.Namespace(
            live=False,
            replay=True,
            full_corpus=False,
            top_k=8,
            cases="eval_cases.json",
        )
        report = build_comparison(args)
        for case in load_cases():
            self.assertIn(f"| {case['id']} |", report)
        self.assertIn("## Aggregate", report)
        self.assertIn("replay_miss", report)


if __name__ == "__main__":
    unittest.main()
