from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import by_id, load_cases, load_corpus
from metrics import check_case
from v2_llm.assistant_llm import GroundedLLMAssistant
from v2_llm.llm_client import FakeClient, ReplayClient, cache_key
from v2_llm.prompts import PROMPT_VERSION
from v2_llm.run_eval_llm import client_for_case


def raw(data) -> str:
    return json.dumps(data)


class V2EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = load_corpus()
        cls.lookup = by_id(cls.corpus)
        cls.cases = {case["id"]: case for case in load_cases()}

    def t9_response(self):
        return {
            "passage_assessment": [
                {"id": "HR-06", "relation": "answers"},
                {"id": "FAQ-01", "relation": "answers"},
            ],
            "claims": [
                {
                    "text": "Submit a time off request through the internal HR system, select the corresponding leave type, and enter the start and end dates.",
                    "evidence": [
                        {
                            "id": "HR-06",
                            "quote": "submit a time off request through the internal HR system",
                        },
                        {
                            "id": "FAQ-01",
                            "quote": "When applying for vacation, select the corresponding leave type and enter the start and end dates.",
                        },
                    ],
                }
            ],
            "not_covered": [],
            "semantic_conflicts": [],
        }

    def test_good_t9_output_passes_and_renders_sections(self) -> None:
        case = self.cases["T9"]
        client = FakeClient({case["question"]: raw(self.t9_response())})
        result = GroundedLLMAssistant(self.corpus).answer(case["question"], client)
        self.assertEqual([], check_case(case, result, "v2", self.corpus))
        self.assertIn("ANSWER", result["rendered"])
        self.assertIn("RISK NOTICE", result["rendered"])
        self.assertIn("SOURCES", result["rendered"])

    def test_fabricated_number_falls_back_to_v1(self) -> None:
        case = self.cases["T9"]
        response = self.t9_response()
        response["claims"][0]["text"] += " Complete it within 99 days."
        client = FakeClient({case["question"]: raw(response)})
        result = GroundedLLMAssistant(self.corpus).answer(case["question"], client)
        self.assertEqual("validator_4_number_not_in_evidence", result["fallback_reason"])
        self.assertEqual("abstain", result["decision"])
        self.assertNotIn("99 days", result["rendered"])

    def test_x1_related_only_becomes_no_direct_support(self) -> None:
        case = self.cases["X1"]
        response = {
            "passage_assessment": [
                {"id": "HR-01", "relation": "related_only"},
                {"id": "HR-02", "relation": "related_only"},
            ],
            "claims": [],
            "not_covered": ["sick"],
            "semantic_conflicts": [],
        }
        client = FakeClient({case["question"]: raw(response)})
        result = GroundedLLMAssistant(self.corpus).answer(case["question"], client)
        self.assertEqual("no_direct_support", result["decision"])
        self.assertEqual([], result["supporting_ids"])
        self.assertTrue(result["related_ids"])
        self.assertIn("CLOSEST RELATED", result["rendered"])

    def test_sources_equal_corpus_text_exactly(self) -> None:
        case = self.cases["T9"]
        client = FakeClient({case["question"]: raw(self.t9_response())})
        result = GroundedLLMAssistant(self.corpus).answer(case["question"], client)
        quoted = [line[2:] for line in result["rendered"].splitlines() if line.startswith("> ")]
        self.assertEqual(
            [self.lookup[item]["text"] for item in result["supporting_ids"]],
            quoted,
        )

    def test_replay_miss_falls_back(self) -> None:
        case = self.cases["T1"]
        with tempfile.TemporaryDirectory() as temp_dir:
            client = ReplayClient(Path(temp_dir) / "missing.json")
            result = GroundedLLMAssistant(self.corpus).answer(case["question"], client)
        self.assertEqual("replay_miss", result["fallback_reason"])
        self.assertEqual(case["v1_actual"]["decision"], result["decision"])

    def test_missing_live_client_falls_back_without_calling_network(self) -> None:
        case = self.cases["T1"]
        result = GroundedLLMAssistant(self.corpus).answer(
            case["question"], None, "no_api_key"
        )
        self.assertEqual("no_api_key", result["fallback_reason"])
        self.assertEqual(case["v1_actual"]["cites"], result["supporting_ids"])

    def test_cache_key_sorts_candidate_ids(self) -> None:
        left = cache_key(PROMPT_VERSION, "model", "question", ["B", "A"])
        right = cache_key(PROMPT_VERSION, "model", "question", ["A", "B"])
        self.assertEqual(left, right)

    def test_bailian_defaults_need_only_dashscope_key(self) -> None:
        args = type("Args", (), {"live": True})()
        with patch.dict(
            os.environ,
            {"DASHSCOPE_API_KEY": "test-key"},
            clear=True,
        ):
            client, reason = client_for_case(args, "question", ["IT-02"])
        self.assertIsNone(reason)
        inner = client.inner
        self.assertEqual("qwen3.8-27b", inner.model)
        self.assertEqual(
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            inner.base_url,
        )
        self.assertEqual(180, inner.timeout_seconds)


if __name__ == "__main__":
    unittest.main()
