"""Domain exceptions for TermitPro — all error categories in one place.

Each exception maps to an HTTP status code via ERROR_STATUS_MAP.
The centralized error handler middleware uses this to return structured errors.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Base ────────────────────────────────────────────────────────────────────

class TermitError(Exception):
    """Base exception for all TermitPro application errors.

    Attributes:
        error_category: coarse bucket for observability / routing
            (``validation``, ``auth``, ``rate_limit``, ``provider``,
             ``agent_loop``, ``safety``, ``tooling``, ``task``,
             ``workspace``, ``runtime``, ``internal``).
        is_recoverable: whether the same request can succeed on retry
            (idempotent call + transient upstream issue → True).
    """
    http_status: int = 500
    code: str = "INTERNAL_ERROR"
    error_category: str = "internal"
    is_recoverable: bool = False


# ── Validation (400) ────────────────────────────────────────────────────────

class ValidationError(TermitError):
    """Invalid input data."""
    http_status = 400
    code = "VALIDATION_ERROR"
    error_category = "validation"


class ToolJsonParseError(ValidationError):
    """Failed to parse tool output as JSON."""
    code = "TOOL_JSON_PARSE_ERROR"


# ── Authentication / Authorization (401/403) ────────────────────────────────

class AuthError(TermitError):
    """Authentication or authorization failure."""
    http_status = 401
    code = "AUTH_ERROR"
    error_category = "auth"


class AgentPermissionError(TermitError):
    """Agent lacks permission for requested action."""
    http_status = 403
    code = "AGENT_PERMISSION_ERROR"


# ── Not Found (404) ─────────────────────────────────────────────────────────

class NotFoundError(TermitError):
    """Requested resource not found."""
    http_status = 404
    code = "NOT_FOUND"


class AgentNotFoundError(NotFoundError):
    """Agent not found in registry."""
    code = "AGENT_NOT_FOUND"


class AgentRunNotFoundError(NotFoundError):
    """Agent run not found."""
    code = "AGENT_RUN_NOT_FOUND"


class TaskNotFoundError(NotFoundError):
    """Task not found."""
    code = "TASK_NOT_FOUND"


# ── Rate Limit / Queue (429) ────────────────────────────────────────────────

class RateLimitError(TermitError):
    """Too many requests or queue full."""
    http_status = 429
    code = "RATE_LIMIT_ERROR"
    error_category = "rate_limit"
    is_recoverable = True


class AgentQueueFullError(RateLimitError):
    """Agent queue is at capacity."""
    code = "AGENT_QUEUE_FULL"


# ── Provider Errors (502) ───────────────────────────────────────────────────

class ProviderError(TermitError):
    """External provider (LLM, search, media) returned an error."""
    http_status = 502
    code = "PROVIDER_ERROR"
    error_category = "provider"
    is_recoverable = True  # transient by default; permanent subclasses override


class MediaProviderError(ProviderError):
    """Media generation/transcription provider error."""
    code = "MEDIA_PROVIDER_ERROR"


class MediaTtsError(ProviderError):
    """TTS provider error."""
    code = "MEDIA_TTS_ERROR"


class MediaVideoError(ProviderError):
    """Video provider error."""
    code = "MEDIA_VIDEO_ERROR"


class MediaTranscribeError(ProviderError):
    """Transcription provider error."""
    code = "MEDIA_TRANSCRIBE_ERROR"


class MediaComposeError(ProviderError):
    """Media composition error."""
    code = "MEDIA_COMPOSE_ERROR"


class MediaLottieError(ProviderError):
    """Lottie animation error."""
    code = "MEDIA_LOTTIE_ERROR"


class MediaStudioError(ProviderError):
    """Media studio pipeline error."""
    code = "MEDIA_STUDIO_ERROR"


class BraveSearchMcpError(ProviderError):
    """Brave Search MCP error."""
    code = "BRAVE_SEARCH_ERROR"


# ── Agent Loop Errors (503) ─────────────────────────────────────────────────

class AgentLoopError(TermitError):
    """Agent loop encountered an unrecoverable error."""
    http_status = 503
    code = "AGENT_LOOP_ERROR"
    error_category = "agent_loop"


class AgentDrainingError(TermitError):
    """Agent service is draining — not accepting new work."""
    http_status = 503
    code = "AGENT_DRAINING"
    error_category = "agent_loop"
    is_recoverable = True  # will resolve when drain finishes


class AgentOnlineError(TermitError):
    """Agent online connectivity error."""
    http_status = 503
    code = "AGENT_ONLINE_ERROR"


# ── Safety / Guardrails (400) ───────────────────────────────────────────────

class GuardrailBlockedError(TermitError):
    """Request blocked by safety guardrails."""
    http_status = 400
    code = "GUARDRAIL_BLOCKED"
    error_category = "safety"


# ── Tool Execution (500) ────────────────────────────────────────────────────

class ToolingError(TermitError):
    """Tool execution or orchestration error."""
    code = "TOOLING_ERROR"
    error_category = "tooling"


# ── Task Execution (500) ────────────────────────────────────────────────────

class TaskExecutionError(TermitError):
    """Task execution failed."""
    code = "TASK_EXECUTION_ERROR"
    error_category = "task"


class PlanningError(TaskExecutionError):
    """Task planning phase error."""
    code = "PLANNING_ERROR"


class VerificationError(TaskExecutionError):
    """Task verification phase error."""
    code = "VERIFICATION_ERROR"


class ExternalError(TaskExecutionError):
    """External dependency error during task execution."""
    code = "EXTERNAL_ERROR"


# ── Workspace Errors (500) ──────────────────────────────────────────────────

class WorkspaceError(TermitError):
    """Workspace operation error."""
    code = "WORKSPACE_ERROR"
    error_category = "workspace"


class SshWorkspaceError(WorkspaceError):
    """SSH workspace error."""
    code = "SSH_WORKSPACE_ERROR"


class AssignmentWorkspaceError(WorkspaceError):
    """Assignment workspace error."""
    code = "ASSIGNMENT_WORKSPACE_ERROR"


# ── Runtime (500) ───────────────────────────────────────────────────────────

class LocalRuntimeError(TermitError):
    """Local runtime (Ollama, etc.) error."""
    code = "LOCAL_RUNTIME_ERROR"
    error_category = "runtime"


class PlaywrightUnavailableError(TermitError):
    """Playwright browser not available."""
    code = "PLAYWRIGHT_UNAVAILABLE"


class WebWorkflowError(TermitError):
    """Browser workflow error."""
    code = "WEB_WORKFLOW_ERROR"


# ══════════════════════════════════════════════════════════════════════════════
# HTTP Status Code Map — used by error handler middleware
# ══════════════════════════════════════════════════════════════════════════════

def get_http_status(exc: Exception) -> int:
    """Extract HTTP status from a TermitError, or return 500 for unknown."""
    if isinstance(exc, TermitError):
        return getattr(exc, "http_status", 500)
    return 500


def get_error_code(exc: Exception) -> str:
    """Extract error code from a TermitError, or return 'INTERNAL_ERROR'."""
    if isinstance(exc, TermitError):
        return getattr(exc, "code", "INTERNAL_ERROR")
    return "INTERNAL_ERROR"


def get_error_category(exc: Exception) -> str:
    """Extract error category from a TermitError, or return 'internal'."""
    if isinstance(exc, TermitError):
        return getattr(exc, "error_category", "internal")
    return "internal"


def get_is_recoverable(exc: Exception) -> bool:
    """Check whether the error is transient/recoverable."""
    if isinstance(exc, TermitError):
        return getattr(exc, "is_recoverable", False)
    return False


@dataclass(frozen=True, slots=True)
class ErrorResponse:
    """Standardized error response shape."""
    error: str       # error code (e.g. "AGENT_NOT_FOUND")
    detail: str      # human-readable message
    status: int      # HTTP status code
