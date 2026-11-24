import "./styles.css";
import { api, type EvalReport, type SkillRow, type State, type Turn } from "./api";

const app = document.querySelector<HTMLDivElement>("#app")!;

const ui = {
  budget: 800,
  simulate: false,
  state: null as State | null,
  turns: [] as Turn[],
  evalReport: null as EvalReport | null,
  selected: null as string | null,
  detail: "" as string,
  error: "" as string,
  busy: false,
};

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => {
    switch (ch) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function skillMatchesLoaded(skill: string, loaded: string[]): boolean {
  return loaded.includes(skill);
}

function renderSkillRows(state: State): string {
  const lastTurn = ui.turns[ui.turns.length - 1];
  const loaded = lastTurn ? lastTurn.loaded : [];
  return state.skills.skills
    .map((skill: SkillRow) => {
      const covered = skill.shadowed.length
        ? `<span class="tag warn">override ${skill.shadowed.map((s) => esc(s.source)).join(", ")}</span>`
        : "";
      const isLoaded = skillMatchesLoaded(skill.name, loaded);
      const deps = skill.dependsOn.length ? `<span class="tag">deps ${esc(skill.dependsOn.join(","))}</span>` : "";
      const files = skill.attached.length ? `<span class="tag">files ${skill.attached.length}</span>` : "";
      return `<tr class="skill-row ${isLoaded ? "loaded" : ""}" data-skill="${esc(skill.name)}">
        <td><code>${esc(skill.name)}</code> ${covered} ${deps} ${files}</td>
        <td><span class="source ${esc(skill.source)}">${esc(skill.sourceLabel)}</span></td>
        <td class="num">${skill.lineTokens}</td>
        <td class="num">${skill.bodyTokens}</td>
        <td>${isLoaded ? '<span class="dot on"></span>' : '<span class="dot"></span>'}</td>
      </tr>`;
    })
    .join("");
}

function renderSkipped(state: State): string {
  if (!state.skills.skipped.length) return '<p class="muted">没有被跳过的 skill。</p>';
  return state.skills.skipped
    .map(
      (row) => `<div class="skip">
        <div><code>${esc(row.path)}</code> <span class="tag bad">${esc(row.source)} skipped</span></div>
        <ul>${row.reasons.map((reason) => `<li>${esc(reason)}</li>`).join("")}</ul>
      </div>`,
    )
    .join("");
}

function renderConflicts(state: State): string {
  if (!state.skills.conflicts.length) return '<p class="muted">没有同名冲突。</p>';
  return state.skills.conflicts
    .map(
      (row) => `<div class="skip">
        <div><code>${esc(row.name)}</code> winner <span class="tag ok">${esc(row.winner.source)}</span>
        shadowed ${row.shadowed.map((s) => `<span class="tag warn">${esc(s.source)}</span>`).join(" ")}</div>
        <div class="muted small">${esc(row.rule)}</div>
      </div>`,
    )
    .join("");
}

function renderTurn(turn: Turn): string {
  const steps = turn.steps
    .map((step) => {
      const kind = step.name ? `${step.type}:${step.name}` : step.type;
      return `<li><span class="tag">${esc(kind)}</span> ${esc(step.detail)}</li>`;
    })
    .join("");
  const files = turn.files.length
    ? `<div class="chips">${turn.files
        .map((f) => `<span class="chip">${esc(f.skill)}/${esc(f.path)} · ${f.bytes}B</span>`)
        .join("")}</div>`
    : "";
  const loaded = turn.loaded.length
    ? `<div class="chips">${turn.loaded.map((name) => `<span class="chip ok">${esc(name)}</span>`).join("")}</div>`
    : "";
  return `<div class="turn">
    <div class="bubble user">${esc(turn.message)}</div>
    <div class="bubble bot">${esc(turn.reply).replace(/\n/g, "<br>")}</div>
    <div class="meta">
      <span class="tag ${turn.mode === "online" ? "ok" : ""}">${esc(turn.mode)}</span>
      <span class="tag">prompt ${turn.prompt.tokens}/${turn.prompt.budget} (${esc(turn.prompt.level)})</span>
      <span class="tag">in ${turn.usage.inputTokens} · out ${turn.usage.outputTokens} · $${turn.usage.costUsd.toFixed(6)}</span>
      <span class="tag">fp ${esc(turn.fingerprint)}</span>
    </div>
    ${loaded}
    ${files}
    <ol class="steps">${steps}</ol>
  </div>`;
}

function renderEval(report: EvalReport | null): string {
  if (!report || !report.variants || Object.keys(report.variants).length === 0) {
    return '<p class="muted">还没有评测结果，点击「运行评测」。</p>';
  }
  const names = Object.keys(report.variants);
  const delta = report.delta;
  const summary = names
    .map(
      (name) =>
        `<div class="metric"><div class="k">${esc(name)}</div><div class="v">${pct(
          report.variants[name].accuracy,
        )}</div><div class="muted small">${report.variants[name].correct}/${
          report.variants[name].total
        } · router ${esc(report.variants[name].router)}</div></div>`,
    )
    .join("");
  const deltaLine = delta
    ? `<div class="delta">改前 ${pct(delta.before)} → 改后 ${pct(delta.after)}（${
        delta.absoluteGain >= 0 ? "+" : ""
      }${(delta.absoluteGain * 100).toFixed(1)}pp） 修复用例：${esc(delta.fixedCases.join(", ") || "无")} 回退用例：${esc(
        delta.regressedCases.join(", ") || "无",
      )}</div>`
    : "";
  const primary = report.variants[names[names.length - 1]];
  const rows = primary.rows
    .map(
      (row) => `<tr class="${row.hit ? "" : "bad-row"}">
        <td>${esc(row.id)}</td>
        <td class="small">${esc(row.text)}</td>
        <td><code>${esc(row.expected ?? "(none)")}</code></td>
        <td><code>${esc(row.predicted ?? "(none)")}</code></td>
        <td class="num">${row.score}</td>
        <td>${row.hit ? "✓" : "✗"}</td>
      </tr>`,
    )
    .join("");
  return `<div class="metrics">${summary}</div>${deltaLine}
    <table class="grid"><thead><tr><th>id</th><th>request</th><th>expected</th><th>predicted</th><th>score</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function renderLlm(state: State): string {
  const totals = state.llm.totals;
  const calls = state.llm.calls
    .slice(0, 5)
    .map(
      (call) =>
        `<tr><td class="small">${esc(call.ts)}</td><td><code>${esc(call.model)}</code></td>
         <td>${esc(call.mode)}</td><td class="num">${call.input_tokens}</td>
         <td class="num">${call.output_tokens}</td><td class="num">$${call.cost_usd.toFixed(6)}</td>
         <td class="small">${esc(call.ok ? call.purpose : call.error.slice(0, 40))}</td></tr>`,
    )
    .join("");
  return `<div class="metrics">
      <div class="metric"><div class="k">mode</div><div class="v">${state.llm.configured ? "online" : "offline"}</div>
        <div class="muted small">LLM_API_KEY ${state.llm.configured ? "已配置" : "未配置，使用确定性路由器"}</div></div>
      <div class="metric"><div class="k">calls</div><div class="v">${totals.calls}</div>
        <div class="muted small">online ${totals.onlineCalls}</div></div>
      <div class="metric"><div class="k">tokens</div><div class="v">${totals.inputTokens}/${totals.outputTokens}</div>
        <div class="muted small">in / out</div></div>
      <div class="metric"><div class="k">cost</div><div class="v">$${totals.costUsd.toFixed(6)}</div>
        <div class="muted small">累计</div></div>
    </div>
    ${
      calls
        ? `<table class="grid"><thead><tr><th>ts</th><th>model</th><th>mode</th><th>in</th><th>out</th><th>cost</th><th>note</th></tr></thead><tbody>${calls}</tbody></table>`
        : '<p class="muted">还没有调用记录。</p>'
    }`;
}

function render(): void {
  const state = ui.state;
  if (!state) {
    app.innerHTML = `<div class="boot">loading…</div>`;
    return;
  }
  const prompt = state.prompt.current;
  const barPct = Math.min(100, (prompt.tokens / Math.max(1, prompt.budget)) * 100);
  app.innerHTML = `
  <header>
    <div class="titles">
      <h1>Skill agent</h1>
      <div class="muted small">渐进式技能披露 · 内置/团队共享/个人 三个来源 · 热更新</div>
    </div>
    <div class="toolbar">
      <label class="ctl">预算 <input id="budget" type="number" min="120" max="4000" step="40" value="${ui.budget}" /></label>
      <label class="ctl"><input id="simulate" type="checkbox" ${ui.simulate ? "checked" : ""}/> 模拟 200 个 skill</label>
      <button id="rescan">重新扫描</button>
      <button id="runEval">运行评测</button>
      <span class="tag ${state.llm.configured ? "ok" : "warn"}">${state.llm.configured ? "online" : "offline"}</span>
      <span class="tag">fp ${esc(state.skills.fingerprint)}</span>
    </div>
  </header>
  ${ui.error ? `<div class="error">${esc(ui.error)}</div>` : ""}
  <section class="meter">
    <div class="meter-head">
      <span>system prompt 技能段：<b>${prompt.tokens}</b> / ${prompt.budget} tokens</span>
      <span class="muted small">level=${esc(prompt.level)} · 列出 ${prompt.included.length} 个 · 省略 ${prompt.omitted.length} 个${
        ui.simulate ? ` · 含模拟 ${state.prompt.simulation.skills} 个` : ""
      }</span>
    </div>
    <div class="bar"><i style="width:${barPct}%"></i></div>
    <details><summary class="small muted">查看注入文本</summary><pre>${esc(prompt.text)}</pre></details>
  </section>
  <main>
    <section class="panel skills">
      <h2>Skills <span class="muted small">${state.skills.skills.length} 个已加载</span></h2>
      <table class="grid"><thead><tr><th>name</th><th>source</th><th class="num">line tok</th><th class="num">body tok</th><th>loaded</th></tr></thead>
      <tbody>${renderSkillRows(state)}</tbody></table>
      <h3>跳过的 skill</h3>
      ${renderSkipped(state)}
      <h3>同名冲突</h3>
      ${renderConflicts(state)}
      <h3>选中详情</h3>
      <pre id="detail">${esc(ui.detail || "点击左侧任意 skill 查看正文 / 附带文件。")}</pre>
    </section>
    <section class="panel chat">
      <h2>对话 <span class="muted small">每一轮都显示加载了哪些 skill、读了哪些文件</span></h2>
      <div id="turns">${ui.turns.map(renderTurn).join("") || '<p class="muted">还没有对话。</p>'}</div>
      <form id="chatForm" class="composer">
        <input id="message" placeholder="例如：把这段短剧台词改得口语一点，剧情别动" autocomplete="off" />
        <button type="submit" ${ui.busy ? "disabled" : ""}>发送</button>
      </form>
    </section>
  </main>
  <section class="panel wide">
    <h2>路由评测 <span class="muted small">改描述前 / 后对比</span></h2>
    ${renderEval(ui.evalReport)}
  </section>
  <section class="panel wide">
    <h2>大模型调用与费用</h2>
    ${renderLlm(state)}
  </section>`;
  bind();
  const turnsBox = document.querySelector<HTMLDivElement>("#turns");
  if (turnsBox) turnsBox.scrollTop = turnsBox.scrollHeight;
}

async function refresh(): Promise<void> {
  try {
    const state = await api.state(ui.budget, ui.simulate);
    ui.state = state;
    if (!ui.turns.length) ui.turns = state.turns.slice(-6);
    ui.error = "";
  } catch (error) {
    ui.error = `加载状态失败：${(error as Error).message}`;
  }
  render();
}

function bind(): void {
  const budget = document.querySelector<HTMLInputElement>("#budget");
  budget?.addEventListener("change", async () => {
    ui.budget = Number(budget.value) || 800;
    await refresh();
  });
  const simulate = document.querySelector<HTMLInputElement>("#simulate");
  simulate?.addEventListener("change", async () => {
    ui.simulate = simulate.checked;
    await refresh();
  });
  document.querySelector<HTMLButtonElement>("#rescan")?.addEventListener("click", async () => {
    try {
      await api.scan();
    } catch (error) {
      ui.error = (error as Error).message;
    }
    await refresh();
  });
  document.querySelector<HTMLButtonElement>("#runEval")?.addEventListener("click", async () => {
    ui.busy = true;
    render();
    try {
      const out = await api.runEval();
      ui.evalReport = out.report;
      ui.error = "";
    } catch (error) {
      ui.error = `评测失败：${(error as Error).message}`;
    }
    ui.busy = false;
    render();
  });
  document.querySelectorAll<HTMLTableRowElement>(".skill-row").forEach((row) => {
    row.addEventListener("click", async () => {
      const name = row.dataset.skill!;
      ui.selected = name;
      try {
        const loaded = await api.loadSkill(name);
        let text = `# ${loaded.name}\norder: ${loaded.order.join(" -> ")}\nattached: ${loaded.attached.join(", ") || "-"}\n\n${loaded.body}`;
        if (loaded.attached.length) {
          const file = await api.readFile(name, loaded.attached[0]);
          text += `\n\n--- ${file.path} (${file.bytes}B) ---\n${file.text.slice(0, 1200)}`;
        }
        ui.detail = text;
      } catch (error) {
        ui.detail = `读取失败：${(error as Error).message}`;
      }
      render();
    });
  });
  const form = document.querySelector<HTMLFormElement>("#chatForm");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.querySelector<HTMLInputElement>("#message");
    const message = input?.value.trim();
    if (!message || ui.busy) return;
    ui.busy = true;
    if (input) input.value = "";
    render();
    try {
      const turn = await api.chat(message, ui.budget, ui.simulate);
      ui.turns.push(turn);
      ui.error = "";
    } catch (error) {
      ui.error = `对话失败：${(error as Error).message}`;
    }
    ui.busy = false;
    await refresh();
  });
}

async function boot(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  const budgetParam = Number(params.get("budget"));
  if (Number.isFinite(budgetParam) && budgetParam > 0) ui.budget = budgetParam;
  ui.simulate = ["1", "true", "on"].includes((params.get("simulate") ?? "").toLowerCase());
  await refresh();
  try {
    ui.evalReport = await api.evalReport();
  } catch {
    ui.evalReport = null;
  }
  render();
}

void boot();
