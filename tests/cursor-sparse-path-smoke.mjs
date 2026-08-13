// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const plugins = [
  ["local-advisor-guardrail", "consult_advisor"],
  ["codex-as-critic-guardrail", "consult_critic"],
  ["codex-as-advisor-guardrail", "consult_advisor"],
  ["claude-as-advisor-guardrail", "consult_advisor"],
  ["claude-as-critic-guardrail", "consult_critic"],
  ["cursor-as-advisor-guardrail", "consult_advisor"],
  ["cursor-as-critic-guardrail", "consult_critic"],
];
const systemRoot = process.env.SystemRoot || "C:\\Windows";
const baseEnvironment = {
  SystemRoot: systemRoot,
  WINDIR: process.env.WINDIR || systemRoot,
  ProgramFiles: process.env.ProgramFiles,
  TEMP: process.env.TEMP,
  TMP: process.env.TMP,
  PATH: "",
  AGENTIC_RAILS_MCP_HOST: "cursor",
  AGENTIC_RAILS_WORKSPACE: root,
};
for (const key of Object.keys(baseEnvironment)) {
  if (baseEnvironment[key] === undefined) delete baseEnvironment[key];
}

const request = [
  { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18" } },
  { jsonrpc: "2.0", method: "notifications/initialized" },
  { jsonrpc: "2.0", id: 2, method: "tools/list" },
].map((message) => JSON.stringify(message)).join("\n") + "\n";

function expand(value, pluginRoot) {
  return value
    .replaceAll("$" + "{PLUGIN_ROOT}", pluginRoot.replaceAll("\\", "/"))
    .replaceAll("$" + "{workspaceFolder}", root.replaceAll("\\", "/"));
}

function runHook(server, command, pluginRoot, environment, input) {
  const prefix = `${server.command} `;
  if (!command.startsWith(prefix)) {
    throw new Error(`hook does not use the absolute Cursor launcher: ${command}`);
  }
  const result = spawnSync(server.command, command.slice(prefix.length).split(" "), {
    cwd: pluginRoot,
    env: environment,
    input: JSON.stringify(input),
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.error || result.status !== 0) {
    throw new Error(`hook failed: ${result.error || result.stderr}`);
  }
  return JSON.parse(result.stdout);
}

async function verifyPlugin(plugin, expectedTool, environment) {
  const pluginRoot = join(root, "plugins", plugin);
  const config = JSON.parse(readFileSync(join(pluginRoot, "mcp.json"), "utf8"));
  const server = Object.values(config.mcpServers)[0];
  const hooks = JSON.parse(readFileSync(join(pluginRoot, "hooks", "cursor-hooks.json"), "utf8")).hooks;

  const context = runHook(
    server,
    hooks.sessionStart.at(-1).command,
    pluginRoot,
    environment,
    { hook_event_name: "sessionStart" },
  );
  if (!context.additional_context) {
    throw new Error(`${plugin} sessionStart hook did not inject protocol context`);
  }

  const child = spawn(server.command, server.args.map((item) => expand(item, pluginRoot)), {
    cwd: expand(server.cwd, pluginRoot),
    env: environment,
    windowsHide: true,
  });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  try {
    const listed = await new Promise((resolveReply, reject) => {
      let output = "";
      child.stdout.setEncoding("utf8");
      child.stdout.on("data", (chunk) => {
        output += chunk;
        const lines = output.split(/\r?\n/);
        output = lines.pop() || "";
        for (const line of lines.filter((item) => item.trim())) {
          const reply = JSON.parse(line);
          if (reply.id === 2) resolveReply(reply);
        }
      });
      child.once("error", reject);
      child.once("exit", (code) => reject(new Error(`${plugin} MCP exited ${code}: ${stderr}`)));
      child.stdin.write(request);
    });
    if (listed?.result?.tools?.[0]?.name !== expectedTool) {
      throw new Error(`${plugin} did not register ${expectedTool}: ${JSON.stringify(listed)}`);
    }

    const denied = runHook(
      server,
      hooks.preToolUse[0].command,
      pluginRoot,
      environment,
      {
        conversation_id: `sparse-path-${plugin}`,
        hook_event_name: "preToolUse",
        tool_name: "Write",
        workspace_roots: [root],
      },
    );
    if (denied.permission !== "deny") {
      throw new Error(`${plugin} live gate did not deny the first write: ${JSON.stringify(denied)}`);
    }
  } finally {
    child.stdin.end();
    await new Promise((resolveExit) => child.once("exit", resolveExit));
  }
}

for (const [plugin, expectedTool] of plugins) {
  await verifyPlugin(plugin, expectedTool, baseEnvironment);
}

const temporaryRoot = mkdtempSync(join(tmpdir(), "agentic-rails-cursor-"));
try {
  const uvCandidates = [
    process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, "Microsoft", "WinGet", "Links", "uv.exe"),
    process.env.USERPROFILE && join(process.env.USERPROFILE, ".local", "bin", "uv.exe"),
    process.env.USERPROFILE && join(process.env.USERPROFILE, ".cargo", "bin", "uv.exe"),
  ].filter(Boolean);
  const uvSource = uvCandidates.find(existsSync);
  if (!uvSource) {
    throw new Error("A real uv.exe is required to build the WinGet-only regression fixture.");
  }
  const localAppData = join(temporaryRoot, "local");
  const winGetLinks = join(localAppData, "Microsoft", "WinGet", "Links");
  mkdirSync(winGetLinks, { recursive: true });
  copyFileSync(uvSource, join(winGetLinks, "uv.exe"));
  const winGetOnlyEnvironment = {
    ...baseEnvironment,
    USERPROFILE: join(temporaryRoot, "profile"),
    LOCALAPPDATA: localAppData,
    APPDATA: join(temporaryRoot, "roaming"),
    PATH: "",
    AGENTIC_RAILS_SKIP_REGISTRY_PATH: "1",
  };
  for (const [plugin, expectedTool] of plugins) {
    await verifyPlugin(plugin, expectedTool, winGetOnlyEnvironment);
  }

  const missingUvPlugin = plugins[0][0];
  const missingUvPluginRoot = join(root, "plugins", missingUvPlugin);
  const missingUvConfig = JSON.parse(readFileSync(join(missingUvPluginRoot, "mcp.json"), "utf8"));
  const missingUvServer = Object.values(missingUvConfig.mcpServers)[0];
  const missingUvRun = spawnSync(
    missingUvServer.command,
    missingUvServer.args.map((item) => expand(item, missingUvPluginRoot)),
    {
      cwd: expand(missingUvServer.cwd, missingUvPluginRoot),
      env: {
        ...winGetOnlyEnvironment,
        LOCALAPPDATA: join(temporaryRoot, "no-uv"),
      },
      input: request,
      encoding: "utf8",
      windowsHide: true,
    },
  );
  if (missingUvRun.status !== 127 || !missingUvRun.stderr.includes("uv was not found after restoring")) {
    throw new Error(`missing-uv launch did not fail clearly: ${missingUvRun.stderr}`);
  }
} finally {
  rmSync(temporaryRoot, { recursive: true, force: true });
}

console.log(`${plugins.length} Cursor adapters passed registry and WinGet-only sparse-PATH launch tests.`);
