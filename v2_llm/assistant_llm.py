"""LLM-assisted pipeline with deterministic validation, decisions, and rendering."""
from __future__ import annotations

from collections import Counter
from typing import Any

from common import Passage, Result, by_id, date_order, full_quote, load_corpus
from v1_rules.assistant_rules import answer as v1_answer
from v1_rules.assistant_rules import conflicts, is_injection, is_sensitive, score
from v2_llm.llm_client import LLMClient, LLMError, ReplayMiss
from v2_llm.prompts import SYSTEM_PROMPT, build_user_prompt
from v2_llm.validators import question_terms_missing_from_claims, validate_response


def select_candidates(
    question: str,
    passages: list[Passage],
    top_k: int = 8,
    full_corpus: bool = False,
) -> list[Passage]:
    if full_corpus:
        return list(passages)
    scored = [
        (score(question, passage), index, passage)
        for index, passage in enumerate(passages)
    ]
    ranked = sorted(
        (item for item in scored if item[0] > 0),
        key=lambda item: (-item[0], item[1]),
    )
    return [passage for _, _, passage in ranked[:top_k]]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _numeric_conflict(passages: list[Passage]) -> bool:
    return any(
        conflicts(passage, other)
        for passage in passages
        for other in passages
        if other is not passage
    )


def _claim_date_key(claim: dict[str, Any], lookup: dict[str, Passage]) -> tuple[bool, str]:
    dates = [
        lookup[evidence["id"]]["date"]
        for evidence in claim["evidence"]
        if evidence["id"] in lookup and lookup[evidence["id"]]["date"]
    ]
    return bool(dates), max(dates) if dates else ""


def _render_validated(
    decision: str,
    data: dict[str, Any],
    supporting: list[Passage],
    related: list[Passage],
    sensitive: bool,
    flagged_ids: list[str],
) -> str:
    lookup = by_id(supporting + related)
    claims = list(data["claims"])
    if decision == "conflict":
        claims.sort(key=lambda claim: _claim_date_key(claim, lookup), reverse=True)

    lines = ["ANSWER"]
    if claims:
        for claim in claims:
            evidence_ids = _dedupe(
                [evidence["id"] for evidence in claim["evidence"]]
            )
            lines.append(f"{claim['text']} [{', '.join(evidence_ids)}]")
    elif decision == "no_direct_support":
        lines.append("The supplied documents do not directly answer the question.")
    else:
        lines.append("No passage in the supplied documents supports an answer.")

    if data["not_covered"]:
        lines.extend(
            ["", "NOT COVERED", "The documents do not mention: " + ", ".join(data["not_covered"])]
        )

    if decision == "no_direct_support":
        lines.extend(
            [
                "",
                "CLOSEST RELATED",
                "Related passages (they do not answer the question): "
                + (", ".join(passage["id"] for passage in related) or "none"),
            ]
        )

    notices: list[str] = []
    if decision == "conflict":
        notices.append(
            "These passages disagree. The assistant has not judged which one applies."
        )
    if data["not_covered"]:
        notices.append(
            "Part of your question is not covered by the documents; the answer above excludes it."
        )
    if sensitive:
        notices.append(
            "Money/deadline topic: please confirm with the document owner before acting."
        )
    if any(passage["date"] is None for passage in supporting + related):
        notices.append("A source has no recorded date and may be outdated.")
    if flagged_ids:
        notices.append(
            "A passage contains instruction-like text; it is quoted as content only and was not followed."
        )
    notices.append("This summary was generated. Check the original text below before acting.")
    lines.extend(["", "RISK NOTICE", *notices])

    lines.extend(["", "SOURCES"])
    shown = supporting + related
    if shown:
        for passage in shown:
            lines.extend([full_quote(passage), ""])
        if lines[-1] == "":
            lines.pop()
    else:
        lines.append("No source passage was used.")
    return "\n".join(lines)


class GroundedLLMAssistant:
    def __init__(
        self,
        passages: list[Passage] | None = None,
        top_k: int = 8,
        full_corpus: bool = False,
    ) -> None:
        self.passages = load_corpus() if passages is None else passages
        self.top_k = top_k
        self.full_corpus = full_corpus
        self.validator_failures: Counter[str] = Counter()

    def candidates(self, question: str) -> list[Passage]:
        return select_candidates(
            question,
            self.passages,
            top_k=self.top_k,
            full_corpus=self.full_corpus,
        )

    def _fallback(self, question: str, reason: str) -> Result:
        result = v1_answer(question, self.passages)
        result["fallback_reason"] = reason
        return result

    def run(
        self,
        question: str,
        client: LLMClient | None,
        no_client_reason: str = "no_api_key",
    ) -> tuple[Result, dict[str, Any] | None]:
        candidates = self.candidates(question)
        if client is None:
            return self._fallback(question, no_client_reason), None
        try:
            raw = client.complete(SYSTEM_PROMPT, build_user_prompt(question, candidates))
        except ReplayMiss:
            return self._fallback(question, "replay_miss"), None
        except LLMError as exc:
            reason = str(exc) if str(exc) else "llm_error"
            return self._fallback(question, reason), None
        except Exception:
            return self._fallback(question, "llm_error"), None

        data, failure = validate_response(
            raw,
            question,
            candidates,
            self.passages,
            self.validator_failures,
        )
        if failure:
            return self._fallback(question, failure), None
        assert data is not None

        lookup = by_id(self.passages)
        evidence_ids = _dedupe(
            [
                evidence["id"]
                for claim in data["claims"]
                for evidence in claim["evidence"]
            ]
        )
        supporting = [lookup[passage_id] for passage_id in evidence_ids]
        has_conflict = bool(data["semantic_conflicts"]) or _numeric_conflict(supporting)
        if data["claims"]:
            decision = "conflict" if has_conflict else "answer"
            if decision == "conflict":
                supporting = date_order(supporting)
        else:
            relations = {
                item["id"]: item["relation"] for item in data["passage_assessment"]
            }
            related = [
                passage
                for passage in candidates
                if relations.get(passage["id"]) == "related_only"
            ]
            decision = "no_direct_support" if related else "abstain"
            supporting = []
        related = related if not data["claims"] else []
        sensitive = is_sensitive(question, supporting)
        displayed = supporting + related
        flagged_ids = [
            passage["id"] for passage in displayed if is_injection(passage)
        ]
        missing = sorted(question_terms_missing_from_claims(question, data, self.passages))
        generated = [claim["text"] for claim in data["claims"]]
        generated.extend(data["not_covered"])
        generated.extend(
            conflict["description"] for conflict in data["semantic_conflicts"]
        )
        rendered = _render_validated(
            decision,
            data,
            supporting,
            related,
            sensitive,
            flagged_ids,
        )
        result: Result = {
            "decision": decision,
            "supporting_ids": [passage["id"] for passage in supporting],
            "related_ids": [passage["id"] for passage in related],
            "disclosed_missing": missing,
            "generated_text": generated,
            "rendered": rendered,
            "sensitive": sensitive,
            "flagged_injection_ids": flagged_ids,
            "fallback_reason": None,
        }
        return result, data

    def answer(
        self,
        question: str,
        client: LLMClient | None,
        no_client_reason: str = "no_api_key",
    ) -> Result:
        result, _ = self.run(question, client, no_client_reason)
        return result
