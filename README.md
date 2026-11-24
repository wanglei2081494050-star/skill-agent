# skill-agent

渐进式技能披露（progressive disclosure）的一个可运行实现：把能力拆成 `skills/<name>/SKILL.md`，
平时只把「名字 + 一句话描述」注入 system prompt，模型需要时再 `load_skill(name)` 读正文，
正文里引用的附带文件再用 `read_skill_file(name, path)` 按需读取。

内含：多目录扫描与同名冲突、坏 frontmatter 跳过并报错、注入长度控制（含 200 技能模拟）、
热更新、路由评测（改描述前/后对比）、演示页面、技能依赖与循环检测、受限脚本执行。

## 一条命令启动

```bash
npm run dev          # 等价于 node scripts/dev.mjs
```

- 后端：Python 标准库 HTTP 服务，无第三方依赖，监听 `http://127.0.0.1:8787`（`/health` 可用）。
- 前端：Vite + TypeScript，监听 `http://127.0.0.1:5173`，把 `/api`、`/health` 代理到后端。
- 首次运行会自动 `npm install`（frontend 目录）。
- 环境要求：Python 3.11+（Windows 上用 `py` 启动）、Node 18+。

单独启动：

```bash
py -m backend.app.server 8787     # 后端
npm --prefix frontend run dev     # 前端
```

其他命令：

```bash
make test        # py -m unittest discover -s tests -t .   （32 个用例）
make smoke       # 端到端自检，不需要 UI
make eval        # 路由评测，写 data/eval/latest.json
make build       # 前端类型检查 + 产物构建
```

## 目录

```
backend/app/
  config.py       路径、来源与优先级、预算、价格、沙箱参数
  frontmatter.py  仅支持 SKILL.md 需要的 YAML 子集；错误逐条列出
  skills.py       多来源扫描、同名冲突、附带文件、指纹式热更新
  inject.py       技能段拼装与四级降级（full/compact/tight/truncated）
  tools.py        load_skill / read_skill_file（路径穿越防护、依赖链、循环检测）
  agent.py        一轮对话：注入 -> 路由 -> 加载正文 -> 读附带文件 -> 回答
  llm.py          OpenAI 兼容客户端；每次调用记录 in/out token 与费用
  bulk.py         200 个模拟技能（只在内存里生成，不落盘）
  sandbox.py      受限脚本执行（超时、禁网、临时目录、输出上限）
  eval.py         路由评测：baseline 与 tuned 两个描述版本对比
  server.py       HTTP API
  smoke.py        端到端自检
frontend/src/     演示页面（列表 / 对话轨迹 / 评测表格 / 调试面板）
skills/
  builtin/        内置技能（7 个）
  team/           团队共享（5 个，含同名覆盖与依赖链、循环依赖演示）
  personal/       个人（3 个，含 1 个坏 frontmatter、1 个同名覆盖）
eval/             路由评测集（20 条）与描述版本
tests/            单元测试（frontmatter / 工具与扫描 / 注入与路由）
```

## 演示脚本对应

| 演示步骤 | 页面位置 |
| --- | --- |
| 1. skill 列表，含被跳过的坏技能、被覆盖的同名技能 | 左栏「Skills」「跳过的 skill」「同名冲突」 |
| 2. 一条请求，先加载正文再读附带文件 | 右栏对话：每轮显示 `load_skill`、`read_skill_file` 步骤与文件 chip |
| 3. 不重启，改正文，下一轮用新内容 | 直接编辑任意 `SKILL.md` 再发一轮，气泡上的 `fp xxxx` 指纹会变 |
| 4. 打开「模拟 200 个 skill」，看注入长度怎么控 | 顶部调试面板开关 + 上方 token 计量条 |
| 5. 改描述前后的路由准确率 | 底部「路由评测」表格 + 「运行评测」按钮 |

调试面板：`重新扫描`、`模拟 200 个 skill`、`预算`（token 上限）、`运行评测`。

## 关键实现

**发现**：三个来源目录各自扫描 `skills/<source>/<name>/SKILL.md`。解析失败（无 frontmatter、
未闭合、tab 缩进、缺 `name`/`description`、name 非 kebab-case、重复键、描述超长）只会把该
技能放进「跳过」列表并附原因，扫描继续，系统照常启动。

**冲突**：同名技能按来源优先级 `personal(30) > team(20) > builtin(10)` 取高者，落败的一份在
列表里以 `override <source>` 标注，永不注入、不可加载。规则写在页面上，评审无需猜。

**注入**：技能段只看「名字 + 描述」。默认预算 800 tokens（`PROMPT_BUDGET_TOKENS`）。超预算时
按四级降级：`full` → 描述截断到 160 字符（`compact`）→ 截断到 48 字符（`tight`）→ 从低优先级
开始丢弃并在末尾写「还有 N 个技能未列出」（`truncated`）。预算极端小时返回一句极短提示，
保证不超过预算。token 数用 `CJK 字符 1 token + 其余字符 4 字符 1 token` 估算（见 `tokens.py`），
故意偏保守。

**200 个技能**：模拟技能只在内存生成（`bulk.py`，确定性命名），不写磁盘。开启后同样的预算
下注入段仍 ≤ 预算：实测 800 token 预算、212 个技能时级别为 `truncated`，列出前若干个、
其余省略。这就是「技能很多时怎么控制长度」的答案：**先压缩描述，再按优先级截断列表，
正文永远不预注入**。

**加载**：`load_skill(name)` 返回正文与依赖正文；`read_skill_file(name, path)` 读附带文件。
安全约束：拒绝绝对路径、盘符、`..` 段、NUL；`resolve()` 后再做一次「必须位于该技能目录内」
的判定，因此符号链接也逃不出去；单文件上限 64KB，二进制拒读。

**热更新**：对全部 `SKILL.md` 与附带文件做 `(路径, mtime_ns, size)` 指纹。每次请求取快照时
比对指纹，变了就重扫，所以改完技能下一轮即生效，不需要重启（页面上 `fp` 值随之变化）。

**依赖（选做）**：frontmatter 里 `depends-on: [a, b]`，加载时 DFS 解析闭包，按依赖优先顺序
一次性返回；成环报 `circular skill dependency: cycle-a -> cycle-b -> cycle-a`，缺依赖只记录
不阻断。

**受限脚本（选做）**：`run_skill_script`（`sandbox.py`）在技能目录的临时副本里执行 `.py`，
10s 超时、环境变量清空、通过注入的 `sitecustomize` 把 `socket` 全部禁用、输出截断 8KB。
这是进程内的 Python 级限制（不是操作系统沙箱），取舍见 `docs/design.md`。

## 路由评测

评测集 `eval/routing_cases.json`（20 条，含 3 条「不需要技能」）。`eval/description_variants.json`
保存两个描述版本，所以「改前/改后」在描述被正式改掉之后依然可复现。

| 版本 | 正确/总数 | 准确率 | 错误用例 |
| --- | --- | --- | --- |
| baseline（两个短剧技能描述都写成「写/改短剧剧本，注意台词、钩子、节奏」） | 18/20 | 90.0% | c01, c02 |
| tuned（一个强调「从零创作、分集大纲、人物小传」，一个强调「只对已有成稿润色、不加情节」） | 20/20 | 100.0% | — |

净提升 +10.0pp，回退 0 条。错误集中在「用户要写新剧本、但同时提到台词/钩子」的请求被引到
改写技能——正是两条 description 共享词汇造成的。

路由器：`router.py` 的 BM25-lite（中文 bigram + 英文词，idf 在技能集上计算，命中 name 加权），
阈值 1.6 以下判为「不需要技能」。**offline 模式**（无 API key）下用它，评测与页面都跑这一套，
所以数字可复现；配置 key 后对话走真实模型，评测仍默认用确定性路由器以保证对比公平。

## 大模型调用与费用

`llm.py` 封装 OpenAI 兼容的 `/chat/completions`，**每次调用无论成功失败都追加一行** JSON 到
`data/llm_calls.jsonl`：`model / mode / input_tokens / output_tokens / cost_usd / latency_ms /
purpose`。费用按 `PRICE_INPUT_PER_M`、`PRICE_OUTPUT_PER_M`（美元 / 百万 token）计算。

```bash
cp .env.example .env      # 填 LLM_API_KEY
py -m backend.app.llm_probe "用一句话说明渐进式技能披露"
```

题目给的临时 key 未随文档带到本机，因此本仓库交付时没有真实在线调用记录：`LLM_API_KEY` 为空
时代码走 offline 路径，并在 `data/llm_calls.jsonl` 写入 `mode=offline, ok=false, error="LLM_API_KEY is not set"`
的记录，绝不伪造 token 与费用。配上 key 后同一条链路（`/api/chat` 或 `llm_probe`）就会产生
真实 token 与费用记录，页面「大模型调用与费用」区直接展示累计值。

## 已知限制

- token 是估算值，不是分词器真实值；预算按估算执行，留了余量。
- offline 路由是词面匹配，不理解语义；换措辞可能误判。真正的语义路由需要在线模型。
- 脚本沙箱是 Python 级限制，无法阻止被执行的脚本做本地文件写入；生产环境应换成容器/作业对象。
- 演示页面只做状态展示，样式朴素（题目要求样式不重要）。

## 提交与身份

提交按「脚手架 → 解析 → 发现 → 注入 → 工具 → 模型 → 对话 → 沙箱 → 接口 → 技能样例 → 评测 →
前端 → 描述调优 → 文档」拆分，每条都有具体范围；未使用 `update`/`fix`/`wip` 之类信息，也没有
改写历史。本仓库的 git 身份是本地配置（`YG <yg@users.noreply.github.com>`），推送到你自己的
仓库前如需显示为你的账号，请先在 GitHub 侧确认邮箱设置。
