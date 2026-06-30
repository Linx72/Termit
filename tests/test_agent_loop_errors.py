"""Tests for agent loop errors — AgentLoopError, AgentDrainingError taxonomy."""

import pytest
from app.domain.exceptions import (
    TermitError,
    AgentLoopError,
    AgentDrainingError,
    get_error_category,
    get_is_recoverable,
    get_http_status,
    get_error_code,
)


class TestAgentLoopErrorTaxonomy:
    """AgentLoopError and AgentDrainingError — categories, recoverable, HTTP status."""

    def test_loop_error_category(self) -> None:
        exc = AgentLoopError("Tool call loop exceeded max iterations")
        assert exc.error_category == "agent_loop"
        assert get_error_category(exc) == "agent_loop"

    def test_loop_error_not_recoverable(self) -> None:
        exc = AgentLoopError("Tool call loop exceeded max iterations")
        assert get_is_recoverable(exc) is False

    def test_draining_error_category(self) -> None:
        exc = AgentDrainingError("Shutting down")
        assert exc.error_category == "agent_loop"
        assert get_error_category(exc) == "agent_loop"

    def test_draining_error_is_recoverable(self) -> None:
        exc = AgentDrainingError("Shutting down")
        assert get_is_recoverable(exc) is True

    def test_both_return_503(self) -> None:
        assert get_http_status(AgentLoopError()) == 503
        assert get_http_status(AgentDrainingError()) == 503

    def test_correct_error_codes(self) -> None:
        assert get_error_code(AgentLoopError()) == "AGENT_LOOP_ERROR"
        assert get_error_code(AgentDrainingError()) == "AGENT_DRAINING"


class TestErrorInheritance:
    """Parent TermitError attribute fallback when subclass doesn't override."""

    def test_agent_loop_is_termit_error(self) -> None:
        exc = AgentLoopError("Something went wrong")
        assert isinstance(exc, TermitError)
        assert exc.http_status == 503

    def test_base_attributes_accessible(self) -> None:
        exc = AgentLoopError("Tool call loop exceeded max iterations")
        assert exc.code == "AGENT_LOOP_ERROR"
        assert exc.http_status == 503
        assert exc.error_category == "agent_loop"
        # is_recoverable defaults to False (not overridden in AgentLoopError)
        assert exc.is_recoverable is False
