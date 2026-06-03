import { TermitRun } from "./agent";
import type { TermitClient } from "./client";
import type { TaskType } from "./types";

export type DevPlatform = "ios" | "macos" | "windows" | "android";

export interface CrossPlatformStackInfo {
  stack_id: string;
  name: string;
  description: string;
  default_platforms: DevPlatform[];
  build_verify: string;
  agent_template_id: string;
}

export interface CrossPlatformAtomicTask {
  step_id: string;
  title: string;
  detail: string;
  platform?: string | null;
  verify_hint: string;
}

export interface CrossPlatformDecomposeResult {
  stack_id: string;
  stack_name: string;
  agent_template_id: string;
  skill_id: string;
  platforms: DevPlatform[];
  build_verify: string;
  atomic_tasks: CrossPlatformAtomicTask[];
  first_step_prompt?: string;
  plan_id?: string;
}

export interface CrossPlatformPrepareResult {
  stack_id: string;
  stack_name: string;
  agent_template_id: string;
  skill_id: string;
  platforms: DevPlatform[];
  build_verify: string;
  step_index: number;
  step_count: number;
  step_id: string;
  step_title: string;
  verify_hint: string;
  prompt: string;
  atomic_tasks: CrossPlatformAtomicTask[];
}

export interface DecomposeCrossPlatformOptions {
  stackId?: string;
  platforms?: DevPlatform[];
  includeGameLoop?: boolean;
  persistPlan?: boolean;
  workspacePath?: string;
}

export interface CrossPlatformPrepareRequest {
  goal: string;
  stack_id?: string;
  platforms?: DevPlatform[];
  include_game_loop?: boolean;
  step_index?: number;
}

export interface RunAtomicDevWorkflowParams {
  goal: string;
  stackId?: string;
  platforms?: DevPlatform[];
  includeGameLoop?: boolean;
  taskType?: TaskType;
  model?: string;
  sessionId?: string;
  agentId?: string;
  templateId?: string;
  stopOnVerifyFailure?: boolean;
  onStep?: (index: number, task: CrossPlatformAtomicTask, prompt: string) => void;
  onVerify?: (
    index: number,
    task: CrossPlatformAtomicTask,
    result: AtomicVerifyResult
  ) => void;
}

export interface AtomicVerifyResult {
  ok: boolean;
  detail: string;
  skipped?: boolean;
}

export interface CrossPlatformStacksResponse {
  stacks: CrossPlatformStackInfo[];
}

export interface CrossPlatformDecomposeRequest {
  goal: string;
  stack_id?: string;
  platforms?: DevPlatform[];
  include_game_loop?: boolean;
  persist_plan?: boolean;
  workspace_path?: string;
}

export interface CrossPlatformPreset {
  id: string;
  labelRu: string;
  labelEn: string;
  goal: string;
  stackId?: string;
  platforms?: DevPlatform[];
  includeGameLoop?: boolean;
}

export const CROSS_PLATFORM_PRESETS: CrossPlatformPreset[] = [
  {
    id: "flutter-mobile",
    labelRu: "Flutter iOS+Android",
    labelEn: "Flutter iOS+Android",
    goal: "Создай MVP Flutter-приложения с общим модулем auth для iOS и Android.",
    stackId: "flutter",
    platforms: ["ios", "android"],
  },
  {
    id: "swift-apple",
    labelRu: "Swift iOS+macOS",
    labelEn: "Swift iOS+macOS",
    goal: "Добавь macOS target к SwiftUI iOS-приложению с общими моделями.",
    stackId: "swift_multiplatform",
    platforms: ["ios", "macos"],
  },
  {
    id: "unity-game",
    labelRu: "Unity игра",
    labelEn: "Unity game",
    goal: "Реализуй game loop и pause menu для iOS и Android в Unity.",
    stackId: "unity",
    platforms: ["ios", "android"],
    includeGameLoop: true,
  },
  {
    id: "maui-desktop",
    labelRu: "MAUI Win+Android",
    labelEn: "MAUI Win+Android",
    goal: "Добавь экран настроек в .NET MAUI для Windows и Android.",
    stackId: "maui",
    platforms: ["windows", "android"],
  },
  {
    id: "godot-mobile",
    labelRu: "Godot iOS+Android",
    labelEn: "Godot iOS+Android",
    goal: "Создай 2D платформер на Godot с export presets для iOS и Android.",
    stackId: "godot",
    platforms: ["ios", "android"],
    includeGameLoop: true,
  },
  {
    id: "kotlin-android",
    labelRu: "Kotlin Compose Android",
    labelEn: "Kotlin Compose Android",
    goal: "MVP Android-приложения на Jetpack Compose с экраном списка.",
    stackId: "kotlin_compose",
    platforms: ["android"],
  },
  {
    id: "react-native-mobile",
    labelRu: "React Native iOS+Android",
    labelEn: "React Native iOS+Android",
    goal: "Expo/React Native приложение с tab navigation для iOS и Android.",
    stackId: "react_native",
    platforms: ["ios", "android"],
  },
  {
    id: "winui-desktop",
    labelRu: "WinUI 3 Windows",
    labelEn: "WinUI 3 Windows",
    goal: "WinUI 3 desktop app с настройками и системным tray.",
    stackId: "winui",
    platforms: ["windows"],
  },
  {
    id: "flutter-all-platforms",
    labelRu: "Flutter 4 платформы",
    labelEn: "Flutter all platforms",
    goal: "Flutter MVP с auth для iOS, Android, macOS и Windows.",
    stackId: "flutter",
    platforms: ["ios", "android", "macos", "windows"],
  },
];

const HEAVY_VERIFY = /xcodebuild|unity batchmode|godot4/i;
const RUNNABLE_VERIFY =
  /^(echo |python3? |npm |npx |flutter |dotnet |\.\/gradlew|swift test)/i;

export async function buildPresetDraft(
  client: TermitClient,
  preset: CrossPlatformPreset
): Promise<string> {
  const plan = await decomposeCrossPlatformTask(client, preset.goal, {
    stackId: preset.stackId,
    platforms: preset.platforms,
    includeGameLoop: preset.includeGameLoop,
  });
  const first = plan.atomic_tasks[0];
  if (!first) {
    return preset.goal;
  }
  const header = [
    `# ${preset.goal}`,
    `Stack: ${plan.stack_name} · template: ${plan.agent_template_id}`,
    `Platforms: ${plan.platforms.join(", ")}`,
    `Steps: ${plan.atomic_tasks.length}`,
    "",
  ].join("\n");
  return `${header}${formatAtomicTaskPrompt(plan, first, 0)}`;
}

export async function ensureAgentForCrossPlatform(
  client: TermitClient,
  templateId: string,
  workspace?: string
): Promise<{ agentId: string; workspace?: string }> {
  const profile = await client.ensureAgentFromTemplate(templateId);
  return { agentId: profile.agent_id, workspace: workspace ?? client.workspace };
}

export async function launchCrossPlatformPreset(
  client: TermitClient,
  preset: CrossPlatformPreset,
  options: Omit<RunAtomicDevWorkflowParams, "goal" | "stackId" | "platforms" | "includeGameLoop"> = {}
): Promise<Awaited<ReturnType<typeof runAtomicDevWorkflow>>> {
  const plan = await decomposeCrossPlatformTask(client, preset.goal, {
    stackId: preset.stackId,
    platforms: preset.platforms,
    includeGameLoop: preset.includeGameLoop,
  });
  let agentId = options.agentId;
  if (!agentId) {
    const agent = await ensureAgentForCrossPlatform(
      client,
      plan.agent_template_id,
      client.workspace
    );
    agentId = agent.agentId;
  }
  return runAtomicDevWorkflow(client, {
    ...options,
    goal: preset.goal,
    stackId: preset.stackId,
    platforms: preset.platforms,
    includeGameLoop: preset.includeGameLoop,
    agentId,
    templateId: plan.agent_template_id,
    stopOnVerifyFailure: options.stopOnVerifyFailure ?? true,
  });
}

export async function listCrossPlatformStacks(
  client: TermitClient
): Promise<CrossPlatformStackInfo[]> {
  const response = await client.listCrossPlatformStacks();
  return response.stacks;
}

export async function prepareCrossPlatformStep(
  client: TermitClient,
  goal: string,
  options: DecomposeCrossPlatformOptions & { stepIndex?: number } = {}
): Promise<CrossPlatformPrepareResult> {
  return client.prepareCrossPlatformStep({
    goal,
    stack_id: options.stackId,
    platforms: options.platforms,
    include_game_loop: options.includeGameLoop,
    step_index: options.stepIndex ?? 0,
  });
}

export async function decomposeCrossPlatformTask(
  client: TermitClient,
  goal: string,
  options: DecomposeCrossPlatformOptions = {}
): Promise<CrossPlatformDecomposeResult> {
  return client.decomposeCrossPlatformTask({
    goal,
    stack_id: options.stackId,
    platforms: options.platforms,
    include_game_loop: options.includeGameLoop,
    persist_plan: options.persistPlan,
    workspace_path: options.workspacePath ?? client.workspace,
  });
}

export function formatAtomicTaskPrompt(
  plan: CrossPlatformDecomposeResult,
  task: CrossPlatformAtomicTask,
  index: number
): string {
  const lines = [
    `[Atomic step ${index + 1}/${plan.atomic_tasks.length}] ${task.title}`,
    `Stack: ${plan.stack_name} (${plan.stack_id})`,
    `Platforms: ${plan.platforms.join(", ")}`,
    "",
    task.detail,
    "",
    `Verify: ${task.verify_hint || plan.build_verify}`,
    "Return only the changes for this step; do not jump ahead to later platforms.",
  ];
  if (task.platform) {
    lines.splice(4, 0, `Target platform: ${task.platform}`);
  }
  return lines.join("\n");
}

export async function verifyAtomicStep(
  client: TermitClient,
  verifyHint: string,
  workspace?: string
): Promise<AtomicVerifyResult> {
  const cmd = verifyHint.trim();
  if (!cmd || cmd.length < 4) {
    return { ok: true, detail: "no verify command", skipped: true };
  }
  if (HEAVY_VERIFY.test(cmd)) {
    return { ok: true, detail: "skipped heavy native verify", skipped: true };
  }
  if (!RUNNABLE_VERIFY.test(cmd) && !cmd.includes("&&")) {
    return { ok: true, detail: "advisory verify only", skipped: true };
  }
  try {
    const result = await client.executeCommand({
      command: cmd,
      path: workspace || client.workspace || ".",
      dry_run: false,
      confirmed: true,
    });
    const ok = !result.executed || result.exit_code === 0;
    return {
      ok,
      detail: result.executed
        ? `exit_code=${result.exit_code}`
        : "not executed",
    };
  } catch (error) {
    return {
      ok: false,
      detail: error instanceof Error ? error.message : String(error),
    };
  }
}

export async function runAtomicDevWorkflow(
  client: TermitClient,
  params: RunAtomicDevWorkflowParams
): Promise<{
  plan: CrossPlatformDecomposeResult;
  steps: Array<{
    task: CrossPlatformAtomicTask;
    response: string;
    sessionId?: string;
    runId?: string;
    verify: AtomicVerifyResult;
  }>;
  aborted: boolean;
}> {
  const plan = await decomposeCrossPlatformTask(client, params.goal, {
    stackId: params.stackId,
    platforms: params.platforms,
    includeGameLoop: params.includeGameLoop,
    workspacePath: client.workspace,
  });

  let agentId = params.agentId;
  if (!agentId && params.templateId) {
    const agent = await ensureAgentForCrossPlatform(client, params.templateId, client.workspace);
    agentId = agent.agentId;
  } else if (!agentId) {
    const agent = await ensureAgentForCrossPlatform(
      client,
      plan.agent_template_id,
      client.workspace
    );
    agentId = agent.agentId;
  }

  let sessionId = params.sessionId;
  const steps: Array<{
    task: CrossPlatformAtomicTask;
    response: string;
    sessionId?: string;
    runId?: string;
    verify: AtomicVerifyResult;
  }> = [];
  let aborted = false;

  for (let index = 0; index < plan.atomic_tasks.length; index += 1) {
    const task = plan.atomic_tasks[index];
    const message = formatAtomicTaskPrompt(plan, task, index);
    params.onStep?.(index, task, message);

    let responseText = "";
    let runId: string | undefined;

    const created = await client.createAgentRun(agentId, {
      input: message,
      session_id: sessionId,
      use_retrieval: true,
      retrieval_path_prefix: client.workspace,
      use_tool_loop: true,
      workspace_scope: client.workspace,
    });
    runId = created.run_id;
    const run = new TermitRun(client, created.run_id, { timeoutSeconds: 900 });
    const record = await run.wait();
    sessionId = record.session_id ?? sessionId;
    responseText = record.response ?? "";

    const verify = await verifyAtomicStep(
      client,
      task.verify_hint || plan.build_verify,
      client.workspace
    );
    params.onVerify?.(index, task, verify);

    await client.recordCrossPlatformStep({
      goal: params.goal,
      stack_id: plan.stack_id,
      step_id: task.step_id,
      step_index: index,
      verify_ok: verify.ok,
      verify_detail: verify.detail,
      plan_id: plan.plan_id,
    });

    steps.push({
      task,
      response: responseText,
      sessionId: record.session_id,
      runId,
      verify,
    });

    if (params.stopOnVerifyFailure !== false && !verify.ok) {
      aborted = true;
      break;
    }
  }

  return { plan, steps, aborted };
}
