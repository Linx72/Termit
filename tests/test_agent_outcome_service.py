"""Tests for agent outcome classification."""

from __future__ import annotations

import unittest

from app.services.agent_outcome_service import (
    OUTCOME_BLOCKED_POLICY,
    OUTCOME_PARTIAL,
    OUTCOME_SUCCESS,
    classify_agent_outcome,
)


class AgentOutcomeServiceTests(unittest.TestCase):
    def test_completed_is_success(self) -> None:
        outcome = classify_agent_outcome(
            state="completed",
            failure_class=None,
            response="done",
            error=None,
        )
        self.assertEqual(outcome, OUTCOME_SUCCESS)

    def test_policy_block(self) -> None:
        outcome = classify_agent_outcome(
            state="failed",
            failure_class="user_rejected",
            response="",
            error="rejected",
        )
        self.assertEqual(outcome, OUTCOME_BLOCKED_POLICY)

    def test_verification_partial(self) -> None:
        outcome = classify_agent_outcome(
            state="failed",
            failure_class="verification_error",
            response="",
            error="tests failed",
        )
        self.assertEqual(outcome, OUTCOME_PARTIAL)


if __name__ == "__main__":
    unittest.main()
