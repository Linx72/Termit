from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    coding = "coding"
    review = "review"
    debug = "debug"
    explain = "explain"
    general = "general"


class TaskState(str, Enum):
    queued = "queued"
    running = "running"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskMode(str, Enum):
    auto = "auto"
    guided = "guided"


class ChatMessage(BaseModel):
    role: str = Field(default="user")
    content: str


class ChatRequest(BaseModel):
    message: str
    task_type: TaskType = TaskType.general
    model: Optional[str] = None
    session_id: Optional[str] = None
    use_memory: bool = True
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1200, ge=64, le=8192)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    provider: str
    model: str
    task_type: TaskType
    session_id: Optional[str] = None
    history_size: int = 0
    attempted_models: list[str] = Field(default_factory=list)
    response: str


class ProviderInfo(BaseModel):
    provider: str
    models: list[str]


class ProviderStatus(BaseModel):
    provider: str
    ok: bool
    detail: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    history: list[ChatMessage]


class SessionClearResponse(BaseModel):
    session_id: str
    cleared: bool


class SessionExportResponse(BaseModel):
    session_id: str
    format: str
    content: str
    message_count: int


class SessionExportFormat(str, Enum):
    markdown = "markdown"
    json = "json"
    txt = "txt"


class ListFilesRequest(BaseModel):
    path: str = "."
    pattern: str = "*"


class ListFilesResponse(BaseModel):
    root: str
    path: str
    files: list[str]


class ReadFileRequest(BaseModel):
    path: str
    max_bytes: int = Field(default=20000, ge=256, le=200000)


class ReadFileResponse(BaseModel):
    path: str
    content: str
    truncated: bool = False


class ToolRiskLevel(str, Enum):
    safe = "safe"
    confirm = "confirm"
    blocked = "blocked"


class ExecuteCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)
    path: str = "."
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    dry_run: bool = False
    confirmed: bool = False


class ExecuteCommandResponse(BaseModel):
    command: str
    path: str
    risk_level: ToolRiskLevel
    policy_reason: str = ""
    executed: bool
    requires_confirmation: bool = False
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0


class ToolAuditEvent(BaseModel):
    timestamp: str
    tool_name: str
    action: str
    risk_level: ToolRiskLevel
    allowed: bool
    reason: str
    command: Optional[str] = None
    path: Optional[str] = None


class TaskCreateRequest(BaseModel):
    input: str = Field(min_length=3, max_length=20000)
    task_type: TaskType = TaskType.general
    mode: TaskMode = TaskMode.auto
    session_id: Optional[str] = None


class TaskEvent(BaseModel):
    event_type: str
    state: TaskState
    message: str
    timestamp: str


class TaskCreateResponse(BaseModel):
    task_id: str
    state: TaskState
    created_at: str


class TaskStatusResponse(BaseModel):
    task_id: str
    state: TaskState
    input: str
    task_type: TaskType
    mode: TaskMode
    session_id: Optional[str] = None
    created_at: str
    updated_at: str
    report: Optional[str] = None
    error: Optional[str] = None
    failure_class: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 0
    events: list[TaskEvent] = Field(default_factory=list)


class TaskCancelResponse(BaseModel):
    task_id: str
    cancelled: bool
    state: TaskState
