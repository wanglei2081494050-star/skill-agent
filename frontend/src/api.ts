export type SkillRow = {
  name: string;
  description: string;
  source: string;
  sourceLabel: string;
  priority: number;
  path: string;
  attached: string[];
  dependsOn: string[];
  lineTokens: number;
  bodyTokens: number;
  shadowed: { source: string; path: string }[];
  mtimeNs: number;
};

export type SkippedRow = { path: string; source: string; reasons: string[] };

export type ConflictRow = {
  name: string;
  winner: { source: string; priority: number };
  shadowed: { source: string; priority: number }[];
  rule: string;
};

export type PromptInfo = {
  tokens: number;
  budget: number;
  level: string;
  included: string[];
  omitted: string[];
  perSkillTokens?: Record<string, number>;
  text: string;
};

export type State = {
  skills: {
    fingerprint: string;
    scannedAt: string;
    sources: { id: string; label: string; path: string; priority: number; dirs: number; loaded: number }[];
    skills: SkillRow[];
    skipped: SkippedRow[];
    conflicts: ConflictRow[];
  };
  prompt: {
    current: PromptInfo;
    withoutSimulation: { tokens: number; level: string; count: number };
    simulation: { enabled: boolean; skills: number };
  };
  llm: {
    configured: boolean;
    totals: { calls: number; onlineCalls: number; inputTokens: number; outputTokens: number; costUsd: number };
    calls: {
      ts: string;
      model: string;
      mode: string;
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
      purpose: string;
      ok: boolean;
      error: string;
    }[];
  };
  turns: Turn[];
};

export type Step = {
  type: string;
  detail: string;
  name?: string;
  args?: Record<string, unknown>;
  top?: [string, number][];
  tokens?: number;
  budget?: number;
  level?: string;
};

export type Turn = {
  id: string;
  ts: string;
  message: string;
  mode: string;
  reply: string;
  steps: Step[];
  loaded: string[];
  files: { skill: string; path: string; bytes: number }[];
  prompt: { tokens: number; budget: number; level: string; included: string[]; omitted: string[] };
  usage: { inputTokens: number; outputTokens: number; costUsd: number; calls: number };
  fingerprint: string;
};

export type EvalRow = {
  id: string;
  category: string;
  text: string;
  expected: string | null;
  predicted: string | null;
  score: number;
  hit: boolean;
  runnerUp: [string, number] | null;
};

export type EvalVariant = {
  variant: string;
  router: string;
  threshold: number;
  total: number;
  correct: number;
  accuracy: number;
  wrong: string[];
  rows: EvalRow[];
  generatedAt: string;
};

export type EvalReport = {
  generatedAt?: string;
  fingerprint?: string;
  variants: Record<string, EvalVariant>;
  delta?: {
    before: number;
    after: number;
    absoluteGain: number;
    fixedCases: string[];
    regressedCases: string[];
  };
  note?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(`bad JSON from ${path}: ${text.slice(0, 120)}`);
  }
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && "error" in payload
        ? String((payload as { error: unknown }).error)
        : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload as T;
}

export const api = {
  health: () => request<{ status: string; scans: number }>("/health"),
  state: (budget: number, simulate: boolean) =>
    request<State>(`/api/state?budget=${budget}&simulate=${simulate ? 1 : 0}`),
  scan: () => request<{ ok: boolean; fingerprint: string; skills: number }>("/api/scan", { method: "POST" }),
  chat: (message: string, budget: number, simulate: boolean) =>
    request<Turn>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message, budget, simulate }),
    }),
  loadSkill: (name: string) =>
    request<{ name: string; body: string; order: string[]; attached: string[] }>("/api/load", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  readFile: (name: string, path: string) =>
    request<{ path: string; bytes: number; text: string }>("/api/file", {
      method: "POST",
      body: JSON.stringify({ name, path }),
    }),
  runScript: (name: string, path: string, args: string[]) =>
    request<{ ok: boolean; exitCode: number | null; stdout: string; stderr: string; error: string }>(
      "/api/script",
      { method: "POST", body: JSON.stringify({ name, path, args }) },
    ),
  evalReport: () => request<EvalReport>("/api/eval"),
  runEval: () => request<{ ok: boolean; report: EvalReport }>("/api/eval/run", { method: "POST" }),
};
