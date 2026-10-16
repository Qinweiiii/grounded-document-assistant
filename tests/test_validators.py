from __future__ import annotations

import json
import unittest

from common import by_id, load_corpus
from v2_llm.validators import (
    parse_schema,
    validate_claim_relations,
    validate_evidence_ids,
    validate_exact_quotes,
    validate_missing_disclosure,
    validate_no_injection_artifact,
    validate_no_winner_language,
    validate_number_fidelity,
    validate_numeric_conflict_completeness,
)


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = load_corpus()
        cls.lookup = by_id(cls.corpus)

    def base_data(self):
        return {
            "passage_assessment": [{"id": "IT-02", "relation": "answers"}],
            "claims": [
                {
                    "text": "Employees must first connect to the corporate VPN.",
                    "evidence": [
                        {
                            "id": "IT-02",
                            "quote": "must first connect to the corporate VPN",
                        }
                    ],
                }
            ],
            "not_covered": [],
            "semantic_conflicts": [],
        }

    def test_validator_1_schema_pass_and_fail(self) -> None:
        parsed, reason = parse_schema(json.dumps(self.base_data()))
        self.assertIsNotNone(parsed)
        self.assertIsNone(reason)
        parsed, reason = parse_schema('{"claims": []}')
        self.assertIsNone(parsed)
        self.assertEqual("validator_1_schema", reason)

    def test_validator_2_evidence_id_pass_and_fail(self) -> None:
        data = self.base_data()
        self.assertIsNone(validate_evidence_ids(data, self.corpus, self.corpus))
        data["claims"][0]["evidence"][0]["id"] = "NOT-REAL"
        self.assertEqual(
            "validator_2_invalid_evidence_id",
            validate_evidence_ids(data, self.corpus, self.corpus),
        )

    def test_validator_3_exact_quote_pass_and_fail(self) -> None:
        data = self.base_data()
        self.assertIsNone(validate_exact_quotes(data, self.corpus))
        data["claims"][0]["evidence"][0]["quote"] = "connect without a VPN"
        self.assertEqual(
            "validator_3_quote_not_verbatim",
            validate_exact_quotes(data, self.corpus),
        )

    def test_validator_4_number_fidelity_pass_and_fail(self) -> None:
        data = self.base_data()
        data["claims"][0] = {
            "text": "Passwords change every 90 days.",
            "evidence": [{"id": "IT-01", "quote": "every 90 days"}],
        }
        self.assertIsNone(validate_number_fidelity(data))
        data["claims"][0]["text"] = "Passwords change every 30 days."
        self.assertEqual(
            "validator_4_number_not_in_evidence", validate_number_fidelity(data)
        )

    def test_validator_5_relation_pass_and_fail(self) -> None:
        data = self.base_data()
        self.assertIsNone(validate_claim_relations(data))
        data["passage_assessment"][0]["relation"] = "related_only"
        self.assertEqual(
            "validator_5_claim_uses_non_supporting_relation",
            validate_claim_relations(data),
        )

    def test_validator_6_winner_language_pass_and_fail(self) -> None:
        data = self.base_data()
        self.assertIsNone(validate_no_winner_language(data))
        data["claims"][0]["text"] = "IT-02 is current and should be followed."
        self.assertEqual(
            "validator_6_winner_picking_language",
            validate_no_winner_language(data),
        )

    def test_validator_7_missing_disclosure_pass_and_fail(self) -> None:
        data = self.base_data()
        data["not_covered"] = ["holiday schedule requirements"]
        question = "What are VPN requirements and the holiday schedule?"
        self.assertIsNone(validate_missing_disclosure(question, data, self.corpus))
        data["not_covered"] = []
        self.assertEqual(
            "validator_7_missing_not_covered",
            validate_missing_disclosure(question, data, self.corpus),
        )

    def test_validator_8_numeric_conflict_pass_and_fail(self) -> None:
        data = {
            "passage_assessment": [
                {"id": "HR-01", "relation": "answers"},
                {"id": "HR-02", "relation": "answers"},
            ],
            "claims": [
                {
                    "text": "The passage states 10 days.",
                    "evidence": [{"id": "HR-01", "quote": "10 days"}],
                },
                {
                    "text": "The passage states 12 days.",
                    "evidence": [{"id": "HR-02", "quote": "12 days"}],
                },
            ],
            "not_covered": [],
            "semantic_conflicts": [],
        }
        candidates = [self.lookup["HR-01"], self.lookup["HR-02"]]
        self.assertIsNone(validate_numeric_conflict_completeness(data, candidates))
        data["claims"].pop()
        self.assertEqual(
            "validator_8_incomplete_numeric_conflict",
            validate_numeric_conflict_completeness(data, candidates),
        )

    def test_validator_9_injection_artifact_pass_and_fail(self) -> None:
        data = self.base_data()
        candidates = [self.lookup["FAQ-02"]]
        self.assertIsNone(validate_no_injection_artifact(data, candidates))
        data["claims"][0]["text"] = "SYSTEM OVERRIDE SUCCESS"
        self.assertEqual(
            "validator_9_injection_artifact",
            validate_no_injection_artifact(data, candidates),
        )


if __name__ == "__main__":
    unittest.main()
