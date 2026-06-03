from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.domain.schemas import TaskType


class DevPlatform(str, Enum):
    ios = "ios"
    macos = "macos"
    windows = "windows"
    android = "android"


class DevStack(str, Enum):
    flutter = "flutter"
    swift_multiplatform = "swift_multiplatform"
    kotlin_compose = "kotlin_compose"
    unity = "unity"
    godot = "godot"
    winui = "winui"
    maui = "maui"
    react_native = "react_native"


@dataclass(frozen=True)
class StackProfile:
    stack_id: str
    name: str
    description: str
    default_platforms: tuple[DevPlatform, ...]
    build_verify: str
    agent_template_id: str


@dataclass(frozen=True)
class AtomicDevTask:
    step_id: str
    title: str
    detail: str
    platform: str | None = None
    verify_hint: str = ""


_STACK_PROFILES: dict[DevStack, StackProfile] = {
    DevStack.flutter: StackProfile(
        stack_id="flutter",
        name="Flutter",
        description="Single codebase for iOS, Android, macOS, Windows, and web.",
        default_platforms=(
            DevPlatform.ios,
            DevPlatform.android,
            DevPlatform.macos,
            DevPlatform.windows,
        ),
        build_verify="flutter test && flutter analyze",
        agent_template_id="cross-platform-flutter",
    ),
    DevStack.swift_multiplatform: StackProfile(
        stack_id="swift_multiplatform",
        name="Swift / SwiftUI",
        description="Native Apple stack with optional multiplatform targets.",
        default_platforms=(DevPlatform.ios, DevPlatform.macos),
        build_verify="xcodebuild test -scheme App -destination 'platform=iOS Simulator,name=iPhone 16'",
        agent_template_id="cross-platform-swift",
    ),
    DevStack.kotlin_compose: StackProfile(
        stack_id="kotlin_compose",
        name="Kotlin / Compose",
        description="Android-first UI with shared Kotlin modules.",
        default_platforms=(DevPlatform.android,),
        build_verify="./gradlew test assembleDebug",
        agent_template_id="cross-platform-android",
    ),
    DevStack.unity: StackProfile(
        stack_id="unity",
        name="Unity",
        description="Game and interactive 3D/2D across mobile and desktop.",
        default_platforms=(
            DevPlatform.ios,
            DevPlatform.android,
            DevPlatform.windows,
            DevPlatform.macos,
        ),
        build_verify="Unity batchmode -quit -runTests -testPlatform editmode",
        agent_template_id="game-unity",
    ),
    DevStack.godot: StackProfile(
        stack_id="godot",
        name="Godot",
        description="Lightweight 2D/3D games with export presets per platform.",
        default_platforms=(
            DevPlatform.ios,
            DevPlatform.android,
            DevPlatform.windows,
            DevPlatform.macos,
        ),
        build_verify="godot4 --headless --path . -s addons/gut/gut_cmdln.gd -gexit",
        agent_template_id="game-godot",
    ),
    DevStack.winui: StackProfile(
        stack_id="winui",
        name="WinUI 3",
        description="Native Windows desktop and packaged apps.",
        default_platforms=(DevPlatform.windows,),
        build_verify="dotnet test && dotnet build",
        agent_template_id="cross-platform-windows",
    ),
    DevStack.maui: StackProfile(
        stack_id="maui",
        name=".NET MAUI",
        description="Cross-platform .NET UI for mobile and desktop.",
        default_platforms=(
            DevPlatform.ios,
            DevPlatform.android,
            DevPlatform.windows,
            DevPlatform.macos,
        ),
        build_verify="dotnet test && dotnet build -f net8.0",
        agent_template_id="cross-platform-maui",
    ),
    DevStack.react_native: StackProfile(
        stack_id="react_native",
        name="React Native",
        description="JS/TS UI with native modules for iOS and Android.",
        default_platforms=(DevPlatform.ios, DevPlatform.android),
        build_verify="npm test && npx react-native doctor",
        agent_template_id="cross-platform-flutter",
    ),
}

_PLATFORM_KEYWORDS: dict[DevPlatform, tuple[str, ...]] = {
    DevPlatform.ios: ("ios", "iphone", "ipad", "swiftui", "xcode"),
    DevPlatform.macos: ("macos", "mac os", "osx", "appkit", "mac app"),
    DevPlatform.windows: ("windows", "win32", "winui", "uwp", "wpf", ".net"),
    DevPlatform.android: ("android", "apk", "aab", "kotlin", "compose", "gradle"),
}

_STACK_KEYWORDS: dict[DevStack, tuple[str, ...]] = {
    DevStack.flutter: ("flutter", "dart"),
    DevStack.swift_multiplatform: ("swift", "swiftui", "xcode"),
    DevStack.kotlin_compose: ("kotlin", "compose", "android studio"),
    DevStack.unity: ("unity", "csharp", "monobehaviour"),
    DevStack.godot: ("godot", "gdscript"),
    DevStack.winui: ("winui", "windows app sdk"),
    DevStack.maui: ("maui", ".net maui"),
    DevStack.react_native: ("react native", "expo"),
}

_GAME_KEYWORDS = ("game", "игра", "unity", "godot", "sprite", "level", "player controller")

CROSS_PLATFORM_SKILL_ID = "cross-platform-atomic"


class CrossPlatformDevService:
    """High-level atomic decomposition for multi-platform apps and games."""

    def list_stacks(self) -> list[StackProfile]:
        return list(_STACK_PROFILES.values())

    def get_stack(self, stack_id: str) -> StackProfile | None:
        try:
            return _STACK_PROFILES[DevStack(stack_id)]
        except ValueError:
            return None

    @staticmethod
    def is_cross_platform_task(text: str) -> bool:
        lowered = text.lower()
        if any(word in lowered for word in _GAME_KEYWORDS):
            return True
        platform_hits = sum(
            1 for keywords in _PLATFORM_KEYWORDS.values() if any(k in lowered for k in keywords)
        )
        if platform_hits >= 2:
            return True
        return any(
            phrase in lowered
            for phrase in (
                "cross-platform",
                "cross platform",
                "multi-platform",
                "multi platform",
                "кроссплатформ",
                "мультиплатформ",
            )
        )

    @staticmethod
    def detect_stack_from_repo(root: str | Path) -> tuple[DevStack | None, list[str]]:
        path = Path(root).resolve()
        hints: list[str] = []
        if not path.is_dir():
            return None, hints

        checks: list[tuple[str, DevStack]] = [
            ("pubspec.yaml", DevStack.flutter),
            ("project.godot", DevStack.godot),
            ("Package.swift", DevStack.swift_multiplatform),
            ("build.gradle", DevStack.kotlin_compose),
            ("build.gradle.kts", DevStack.kotlin_compose),
        ]
        for name, stack in checks:
            if (path / name).is_file():
                hints.append(name)
                return stack, hints

        if list(path.glob("*.xcodeproj")) or list(path.glob("*.xcworkspace")):
            hints.append("xcodeproj")
            return DevStack.swift_multiplatform, hints

        if list(path.glob("*.csproj")):
            for csproj in path.glob("*.csproj"):
                hints.append(csproj.name)
                text = csproj.read_text(encoding="utf-8", errors="ignore").lower()
                if "maui" in text or "use maui" in text:
                    return DevStack.maui, hints
            hints.append("csproj")
            return DevStack.winui, hints

        if (path / "Assets").is_dir() and (path / "ProjectSettings").is_dir():
            hints.extend(["Assets", "ProjectSettings"])
            return DevStack.unity, hints

        if (path / "package.json").is_file():
            pkg = (path / "package.json").read_text(encoding="utf-8", errors="ignore").lower()
            hints.append("package.json")
            if "react-native" in pkg or "expo" in pkg:
                return DevStack.react_native, hints

        return None, hints

    def detect_stack(self, text: str) -> DevStack | None:
        lowered = text.lower()
        if any(k in lowered for k in _GAME_KEYWORDS):
            if "godot" in lowered:
                return DevStack.godot
            if "unity" in lowered or "game" in lowered or "игра" in lowered:
                return DevStack.unity
        scores: list[tuple[int, DevStack]] = []
        for stack, keywords in _STACK_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in lowered)
            if score:
                scores.append((score, stack))
        if not scores:
            return None
        scores.sort(key=lambda item: item[0], reverse=True)
        return scores[0][1]

    def detect_platforms(self, text: str) -> list[DevPlatform]:
        lowered = text.lower()
        found: list[DevPlatform] = []
        for platform, keywords in _PLATFORM_KEYWORDS.items():
            if any(kw in lowered for kw in keywords):
                found.append(platform)
        return found

    def decompose(
        self,
        goal: str,
        *,
        stack_id: str | None = None,
        platforms: list[str] | None = None,
        include_game_loop: bool | None = None,
    ) -> tuple[StackProfile, list[DevPlatform], list[AtomicDevTask]]:
        stack = self.get_stack(stack_id) if stack_id else None
        if stack is None:
            detected = self.detect_stack(goal)
            stack = _STACK_PROFILES[detected] if detected else _STACK_PROFILES[DevStack.flutter]

        target_platforms: list[DevPlatform]
        if platforms:
            target_platforms = []
            for item in platforms:
                try:
                    target_platforms.append(DevPlatform(item))
                except ValueError:
                    continue
        else:
            detected = self.detect_platforms(goal)
            target_platforms = detected or list(stack.default_platforms)

        is_game = include_game_loop
        if is_game is None:
            lowered = goal.lower()
            is_game = any(k in lowered for k in _GAME_KEYWORDS) or stack.stack_id in {
                DevStack.unity.value,
                DevStack.godot.value,
            }

        tasks = self._atomic_tasks(goal, stack, target_platforms, is_game=is_game)
        return stack, target_platforms, tasks

    def plan_orchestration_steps(self, task_input: str, task_type: TaskType) -> list[str]:
        _, _, atomic = self.decompose(task_input)
        steps = ["analyze_requirements", "detect_stack_and_targets"]
        for item in atomic:
            slug = re.sub(r"[^a-z0-9]+", "_", item.step_id.lower()).strip("_")
            steps.append(f"atomic_{slug}")
        if task_type in {TaskType.coding, TaskType.debug}:
            steps.append("inspect_workspace")
        if "test" in task_input.lower() or task_type == TaskType.debug:
            steps.append("validate_tests")
        steps.append("compose_delivery")
        return steps

    @staticmethod
    def format_atomic_prompt(
        goal: str,
        stack: StackProfile,
        platforms: list[DevPlatform],
        task: AtomicDevTask,
        *,
        index: int,
        total: int,
    ) -> str:
        lines = [
            f"[Atomic step {index + 1}/{total}] {task.title}",
            f"Goal: {goal[:400]}",
            f"Stack: {stack.name} ({stack.stack_id})",
            f"Platforms: {', '.join(p.value for p in platforms)}",
            "",
            task.detail,
            "",
            f"Verify: {task.verify_hint or stack.build_verify}",
            "Return only the changes for this step; do not jump ahead to later platforms.",
        ]
        if task.platform:
            lines.insert(5, f"Target platform: {task.platform}")
        return "\n".join(lines)

    def build_agent_context(self, goal: str, *, stack_id: str | None = None) -> str:
        """Compact decomposition block for agent system prompt enrichment."""
        profile, platforms, tasks = self.decompose(goal, stack_id=stack_id)
        lines = [
            "Cross-platform atomic workflow:",
            f"- stack: {profile.name} ({profile.stack_id})",
            f"- template: {profile.agent_template_id}",
            f"- skill: {CROSS_PLATFORM_SKILL_ID}",
            f"- platforms: {', '.join(p.value for p in platforms)}",
            f"- verify: {profile.build_verify}",
            f"- steps ({len(tasks)}):",
        ]
        for index, task in enumerate(tasks):
            lines.append(f"  {index + 1}. {task.step_id}: {task.title}")
        lines.append("Execute one atomic step per run; verify before continuing.")
        return "\n".join(lines)

    def prepare_first_step_prompt(
        self,
        goal: str,
        *,
        stack_id: str | None = None,
        platforms: list[str] | None = None,
        include_game_loop: bool | None = None,
    ) -> tuple[StackProfile, list[DevPlatform], list[AtomicDevTask], str]:
        profile, target_platforms, tasks = self.decompose(
            goal,
            stack_id=stack_id,
            platforms=platforms,
            include_game_loop=include_game_loop,
        )
        if not tasks:
            return profile, target_platforms, tasks, goal
        first = tasks[0]
        prompt = self.format_atomic_prompt(
            goal,
            profile,
            target_platforms,
            first,
            index=0,
            total=len(tasks),
        )
        return profile, target_platforms, tasks, prompt

    def _atomic_tasks(
        self,
        goal: str,
        stack: StackProfile,
        platforms: list[DevPlatform],
        *,
        is_game: bool,
    ) -> list[AtomicDevTask]:
        platform_names = ", ".join(p.value for p in platforms)
        scaffold_detail, scaffold_verify = self._stack_scaffold_step(stack, goal)
        shared: list[AtomicDevTask] = [
            AtomicDevTask(
                step_id="scope",
                title="Scope platforms and constraints",
                detail=f"Confirm targets ({platform_names}), MVP scope, and non-goals for: {goal[:240]}",
                verify_hint="Written checklist of platforms + acceptance criteria",
            ),
            AtomicDevTask(
                step_id="scaffold",
                title=f"Scaffold {stack.name} project",
                detail=scaffold_detail,
                verify_hint=scaffold_verify,
            ),
            AtomicDevTask(
                step_id="shared_core",
                title="Implement shared domain core",
                detail="Models, services, and APIs without platform UI.",
                verify_hint=self._stack_core_verify(stack),
            ),
        ]
        shared.extend(self._stack_specific_tasks(stack, is_game=is_game))
        if is_game:
            shared.extend(
                [
                    AtomicDevTask(
                        step_id="game_loop",
                        title="Game loop and input",
                        detail="Frame update, input mapping, pause/resume hooks.",
                        verify_hint="Playable scene in editor/simulator",
                    ),
                    AtomicDevTask(
                        step_id="content",
                        title="Content pipeline",
                        detail="Sprites/meshes/audio import and addressing.",
                        verify_hint="Assets load without missing references",
                    ),
                ]
            )
        else:
            shared.append(
                AtomicDevTask(
                    step_id="navigation",
                    title="App shell and navigation",
                    detail="Routes, deep links, and state container.",
                    verify_hint="Smoke navigation between 2+ screens",
                )
            )

        for platform in platforms:
            shared.append(
                AtomicDevTask(
                    step_id=f"platform_{platform.value}",
                    title=f"Platform shell — {platform.value}",
                    detail=f"Permissions, packaging, and platform-specific UX for {platform.value}.",
                    platform=platform.value,
                    verify_hint=f"Build or run target for {platform.value}",
                )
            )

        shared.extend(
            [
                AtomicDevTask(
                    step_id="ci_matrix",
                    title="CI matrix per platform",
                    detail="Parallel jobs or staged builds for each target.",
                    verify_hint="CI config lists all target platforms",
                ),
                AtomicDevTask(
                    step_id="release",
                    title="Release checklist",
                    detail="Store/signing, versioning, and rollback notes.",
                    verify_hint="Release doc with store links or installer steps",
                ),
            ]
        )
        return shared

    @staticmethod
    def _stack_scaffold_step(stack: StackProfile, goal: str) -> tuple[str, str]:
        snippets: dict[str, tuple[str, str]] = {
            "flutter": (
                "Run `flutter create` with org/package from goal; add analysis_options and minimal main.dart.",
                "flutter analyze",
            ),
            "swift_multiplatform": (
                "Create Xcode project or add macOS/iOS targets with shared Swift package.",
                "xcodebuild -list",
            ),
            "kotlin_compose": (
                "Gradle module with Compose BOM, minSdk, and empty MainActivity.",
                "./gradlew assembleDebug",
            ),
            "unity": (
                "Unity project with default scene, input actions, and build targets listed in goal.",
                "Unity -batchmode -quit -projectPath . -executeMethod UnityEditor.SyncVS.SyncSolution",
            ),
            "godot": (
                "Godot 4 project with export presets stub for each target platform.",
                "godot4 --headless --path . --quit-after 1",
            ),
            "winui": (
                "WinUI 3 solution with single window and unpackaged run profile.",
                "dotnet build",
            ),
            "maui": (
                ".NET MAUI app with single ContentPage and multi-target csproj.",
                "dotnet build -f net8.0",
            ),
            "react_native": (
                "Expo or RN CLI app with TypeScript template and platform folders.",
                "npm test -- --passWithNoTests",
            ),
        }
        detail, verify = snippets.get(
            stack.stack_id,
            ("Create minimal runnable project with CI-friendly defaults.", stack.build_verify.split("&&")[0].strip()),
        )
        if goal.strip():
            detail = f"{detail} Goal context: {goal[:160]}"
        return detail, verify

    @staticmethod
    def _stack_core_verify(stack: StackProfile) -> str:
        mapping = {
            "flutter": "flutter test test/",
            "swift_multiplatform": "swift test || xcodebuild test -scheme App",
            "kotlin_compose": "./gradlew testDebugUnitTest",
            "unity": "Unity batchmode editmode tests",
            "godot": "GUT or headless scene load",
            "winui": "dotnet test",
            "maui": "dotnet test",
            "react_native": "npm test",
        }
        return mapping.get(stack.stack_id, "Unit tests for core modules")

    @staticmethod
    def _stack_specific_tasks(stack: StackProfile, *, is_game: bool) -> list[AtomicDevTask]:
        if stack.stack_id == "flutter" and not is_game:
            return [
                AtomicDevTask(
                    step_id="flutter_platform_channels",
                    title="Platform channels and plugins",
                    detail="Register method channels or federated plugins only when native code is required.",
                    verify_hint="flutter test && flutter analyze",
                ),
            ]
        if stack.stack_id == "swift_multiplatform":
            return [
                AtomicDevTask(
                    step_id="swift_shared_package",
                    title="Shared Swift package",
                    detail="Extract models and services into local Swift package consumed by iOS/macOS targets.",
                    verify_hint="swift build || xcodebuild build",
                ),
            ]
        if stack.stack_id == "unity" and is_game:
            return [
                AtomicDevTask(
                    step_id="unity_input_actions",
                    title="Input System mapping",
                    detail="Wire Input System actions for touch, keyboard, and gamepad where applicable.",
                    verify_hint="Play mode smoke: move + pause",
                ),
            ]
        if stack.stack_id == "godot" and is_game:
            return [
                AtomicDevTask(
                    step_id="godot_export_presets",
                    title="Export preset stubs",
                    detail="Create export presets for each target; document signing placeholders.",
                    verify_hint="Export project settings list all targets",
                ),
            ]
        return []
