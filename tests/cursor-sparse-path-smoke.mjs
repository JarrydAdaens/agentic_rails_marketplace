// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
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

const sparseEnvironment = {
  SystemRoot: process.env.SystemRoot || "C:\\Windows",
  WINDIR: process.env.WINDIR || "C:\\Windows",
  USERPROFILE: process.env.USERPROFILE,
  ProgramFiles: process.env.ProgramFiles,
  LocalAppData: process.env.LocalAppData,
  TEMP: process.env.TEMP,
  TMP: process.env.TMP,
  PATH: "",
  AGENTIC_RAILS_MCP_HOST: "cursor",
  AGENTIC_RAILS_WORKSPACE: root,
};
for (const key of Object.keys(sparseEnvironment)) {
  if (sparseEnvironment[key] === undefined) delete sparseEnvironment[key];
}

const request = [
  { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18" } },
  { jsonrpc: "2.0", method: "notifications/initialized" },
  { jsonrpc: "2.0", id: 2, method: "tools/list" },
].map((message) => JSON.stringify(message)).join("\n") + "\n";

for (const [plugin, expectedTool] of plugins) {
  const pluginRoot = join(root, "plugins", plugin);
  const config = JSON.parse(readFileSync(join(pluginRoot, "mcp.json"), "utf8"));
  const server = Object.values(config.mcpServers)[0];
  const expand = (value) => value
    .replaceAll("${PLUGIN_ROOT}", pluginRoot.replaceAll("\\", "/"))
    .replaceAll("${workspaceFolder}", root.replaceAll("\\", "/"));
  const completed = spawnSync(server.command, server.args.map(expand), {
    cwd: expand(server.cwd),
    env: sparseEnvironment,
    input: request,
    encoding: "utf8",
    windowsHide: true,
  });
  if (completed.error || completed.status !== 0) {
    throw new Error(`${plugin} MCP launch failed: ${completed.error || completed.stderr}`);
  }
  const responseLines = completed.stdout.split(/\r?\n/).filter((line) => line.trim());
  if (responseLines.length === 0) {
    throw new Error(`${plugin} MCP returned no protocol response: ${completed.stderr}`);
  }
  const replies = responseLines.map(JSON.parse);
  const listed = replies.find((reply) => reply.id === 2);
  if (listed?.result?.tools?.[0]?.name !== expectedTool) {
    throw new Error(`${plugin} did not register ${expectedTool}: ${completed.stdout}`);
  }

  const hooks = JSON.parse(readFileSync(join(pluginRoot, "hooks", "cursor-hooks.json"), "utf8")).hooks;
  const context = hooks.sessionStart.at(-1).command;
  const commandPrefix = `${server.command} `;
  if (!context.startsWith(commandPrefix)) {
    throw new Error(`${plugin} hook does not use the absolute Cursor launcher: ${context}`);
  }
  const hookRun = spawnSync(server.command, context.slice(commandPrefix.length).split(" "), {
    cwd: pluginRoot,
    env: sparseEnvironment,
    input: JSON.stringify({ hook_event_name: "sessionStart" }),
    encoding: "utf8",
    windowsHide: true,
  });
  if (hookRun.error || hookRun.status !== 0) {
    throw new Error(`${plugin} sessionStart hook failed: ${hookRun.error || hookRun.stderr}`);
  }
  const hookOutput = JSON.parse(hookRun.stdout);
  if (!hookOutput.additional_context) {
    throw new Error(`${plugin} sessionStart hook did not inject protocol context`);
  }
}

const missingUvRoot = join(root, "tests", "no-uv-installed-here");
const [missingUvPlugin] = plugins[0];
const missingUvPluginRoot = join(root, "plugins", missingUvPlugin);
const missingUvConfig = JSON.parse(readFileSync(join(missingUvPluginRoot, "mcp.json"), "utf8"));
const missingUvServer = Object.values(missingUvConfig.mcpServers)[0];
const expandMissingUv = (value) => value
  .replaceAll("${PLUGIN_ROOT}", missingUvPluginRoot.replaceAll("\\", "/"))
  .replaceAll("${workspaceFolder}", root.replaceAll("\\", "/"));
const missingUvRun = spawnSync(missingUvServer.command, missingUvServer.args.map(expandMissingUv), {
  cwd: expandMissingUv(missingUvServer.cwd),
  env: {
    SystemRoot: sparseEnvironment.SystemRoot,
    WINDIR: sparseEnvironment.WINDIR,
    USERPROFILE: missingUvRoot,
    LocalAppData: missingUvRoot,
    PATH: "",
  },
  input: request,
  encoding: "utf8",
  windowsHide: true,
});
if (missingUvRun.status !== 127 || !missingUvRun.stderr.includes("uv was not found")) {
  throw new Error(`missing-uv launch did not fail clearly: ${missingUvRun.stderr}`);
}

console.log(`${plugins.length} Cursor MCP launchers and hooks passed with an empty PATH.`);
