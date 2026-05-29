from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: list[str]
    default_model: str
    code_model: str
    analysis_model: str
    default_fallback_model: str
    code_fallback_model: str
    analysis_fallback_model: str
    ollama_base_url: str
    openai_compat_base_url: str
    openai_compat_api_key: str
    memory_backend: str
    memory_sqlite_path: str
    memory_max_messages: int


def get_settings() -> Settings:
    return Settings(
        host=os.getenv("TERMIT_HOST", "0.0.0.0"),
        port=int(os.getenv("TERMIT_PORT", "8765")),
        allowed_origins=_split_csv(os.getenv("TERMIT_ALLOWED_ORIGINS", "*")),
        default_model=os.getenv("TERMIT_DEFAULT_MODEL", "ollama:deepseek-coder"),
        code_model=os.getenv("TERMIT_CODE_MODEL", "ollama:deepseek-coder"),
        analysis_model=os.getenv("TERMIT_ANALYSIS_MODEL", "ollama:qwen2.5-coder"),
        default_fallback_model=os.getenv(
            "TERMIT_DEFAULT_FALLBACK_MODEL",
            "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
        ),
        code_fallback_model=os.getenv(
            "TERMIT_CODE_FALLBACK_MODEL",
            "openai_compat:deepseek-ai/deepseek-coder-33b-instruct",
        ),
        analysis_fallback_model=os.getenv(
            "TERMIT_ANALYSIS_FALLBACK_MODEL",
            "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        openai_compat_base_url=os.getenv("OPENAI_COMPAT_BASE_URL", "http://localhost:8001"),
        openai_compat_api_key=os.getenv("OPENAI_COMPAT_API_KEY", ""),
        memory_backend=os.getenv("TERMIT_MEMORY_BACKEND", "sqlite"),
        memory_sqlite_path=os.getenv("TERMIT_MEMORY_SQLITE_PATH", "./termit_memory.db"),
        memory_max_messages=int(os.getenv("TERMIT_MEMORY_MAX_MESSAGES", "40")),
    )
