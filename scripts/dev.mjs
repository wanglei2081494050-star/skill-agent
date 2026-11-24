#!/usr/bin/env node
// Single-command dev launcher: backend (stdlib Python HTTP server) + Vite dev server.
// Usage: npm run dev   |   node scripts/dev.mjs
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const API_PORT = process.env.PORT ?? "8787";
const isWindows = process.platform === "win32";
const pythonCandidates = isWindows ? ["py", "python"] : ["python3", "python"];

const children = [];
let shuttingDown = false;

function log(prefix, chunk) {
  for (const line of chunk.toString().split(/\r?\n/)) {
    if (line.trim()) process.stdout.write(`[${prefix}] ${line}\n`);
  }
}

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(code), 200);
}

function startPython(args, prefix) {
  const [cmd, ...rest] = args;
  const child = spawn(cmd, rest, { cwd: repoRoot, shell: isWindows, env: process.env });
  child.stdout.on("data", (c) => log(prefix, c));
  child.stderr.on("data", (c) => log(prefix, c));
  child.on("exit", (code) => {
    if (!shuttingDown) {
      console.error(`[${prefix}] exited with code ${code}`);
      shutdown(code ?? 1);
    }
  });
  children.push(child);
  return child;
}

async function waitForHealth(url, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  return false;
}

async function main() {
  const python = pythonCandidates[0];
  startPython([python, "-m", "backend.app.server", API_PORT], "api");

  const healthy = await waitForHealth(`http://127.0.0.1:${API_PORT}/health`);
  if (!healthy) {
    console.error("[dev] backend did not become healthy in time");
    shutdown(1);
    return;
  }
  console.log(`[dev] backend ready on http://127.0.0.1:${API_PORT}`);

  if (!existsSync(join(repoRoot, "frontend", "node_modules"))) {
    console.log("[dev] installing frontend dependencies (first run)…");
    const install = spawn(isWindows ? "npm.cmd" : "npm", ["install"], {
      cwd: join(repoRoot, "frontend"),
      stdio: "inherit",
      shell: isWindows,
    });
    await new Promise((resolve) => install.on("exit", resolve));
  }

  const vite = spawn(isWindows ? "npm.cmd" : "npm", ["run", "dev"], {
    cwd: join(repoRoot, "frontend"),
    env: { ...process.env, API_ORIGIN: `http://127.0.0.1:${API_PORT}` },
    shell: isWindows,
  });
  vite.stdout.on("data", (c) => log("web", c));
  vite.stderr.on("data", (c) => log("web", c));
  vite.on("exit", (code) => {
    if (!shuttingDown) {
      console.error(`[web] exited with code ${code}`);
      shutdown(code ?? 1);
    }
  });
  children.push(vite);

  console.log("[dev] demo page: http://127.0.0.1:5173");
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

main().catch((error) => {
  console.error(error);
  shutdown(1);
});
