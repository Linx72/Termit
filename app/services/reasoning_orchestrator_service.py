"""Extended thinking for plan/composer: draft -> critique -> execute context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.domain.schemas import ChatMessage
from app.services.llm_caller_service import LlmCallerService


@dataclass(frozen=True)
class ReasoningPassResult:
    draft: str
    critique: str
    refined_plan: str
    draft_model: str
    critic_model: str

    def as_dict(self) -> dict[str, object]:
        return {
            "draft": self.draft,
            "critique": self.critique,
            "refined_plan": self.refined_plan,
            "draft_model": self.draft_model,
            "critic_model": self.critic_model,
        }

    def memory_block(self) -> str:
        return (
            "Reasoning pass (draft -> critique -> refined plan):\n"
            f"Draft:\n{self.draft[:1500]}\n\n"
            f"Critique:\n{self.critique[:1000]}\n\n"
            f"Refined plan:\n{self.refined_plan[:2000]}"
        )


class ReasoningOrchestratorService:
    def __init__(
        self,
        *,
        llm_caller: LlmCallerService,
        draft_model: str,
        critic_model: str,
    ) -> None:
        self._llm_caller = llm_caller
        self._draft_model = draft_model.strip()
        self._critic_model = critic_model.strip()

    def run_reasoning_pass(self, *, task: str, repo_context: str = "") -> ReasoningPassResult:
        context_block = f"\nRepo context:\n{repo_context[:3000]}\n" if repo_context.strip() else ""
        draft_prompt = (
            "Create a concise execution plan for the coding agent.\n"
            "Include: files to inspect, likely changes, verify command, risks.\n"
            f"Task:\n{task[:2500]}{context_block}"
        )
        draft = self._llm_caller.call(
            self._draft_model,
            draft_prompt,
            system="You are a senior planner for a local coding agent.",
            temperature=0.3,
        )
        critique_prompt = (
            "Critique the plan for gaps, unsafe steps, missing verify, and over-scoping.\n"
            f"Task:\n{task[:2000]}\n\nPlan:\n{draft[:3000]}\n"
            "Respond with bullet critique only."
        )
        critique = self._llm_caller.call(
            self._critic_model,
            critique_prompt,
            system="You are a strict reviewer for agent execution plans.",
            temperature=0.1,
        )
        refine_prompt = (
            "Rewrite the plan incorporating critique. Keep it actionable for tool loop.\n"
            f"Original plan:\n{draft[:2500]}\n\nCritique:\n{critique[:2000]}\n"
            "Return final plan only."
        )
        refined = self._llm_caller.call(
            self._draft_model,
            refine_prompt,
            system="You refine agent plans into minimal executable steps.",
            temperature=0.2,
        )
        return ReasoningPassResult(
            draft=draft.strip(),
            critique=critique.strip(),
            refined_plan=refined.strip(),
            draft_model=self._draft_model,
            critic_model=self._critic_model,
        )

    def build_plan_messages(self, result: ReasoningPassResult) -> list[ChatMessage]:
        return [
            ChatMessage(
                role="system",
                content=(
                    "Plan mode: execute the refined plan with read-only analysis first, "
                    "then tools only when user confirms execution."
                ),
            ),
            ChatMessage(role="user", content=result.memory_block()),
        ]
