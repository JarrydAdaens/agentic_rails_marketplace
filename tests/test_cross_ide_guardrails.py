# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class MarketplaceMatrixTests(unittest.TestCase):
    def catalog_names(self, relative: str) -> set[str]:
        catalog = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        return {entry["name"] for entry in catalog["plugins"]}

    def test_each_lead_can_install_both_roles_from_other_providers(self):
        claude = self.catalog_names(".claude-plugin/marketplace.json")
        codex = self.catalog_names(".agents/plugins/marketplace.json")
        cursor = self.catalog_names(".cursor-plugin/marketplace.json")
        self.assertTrue({"codex-as-advisor-guardrail", "codex-as-critic-guardrail", "cursor-as-advisor-guardrail", "cursor-as-critic-guardrail"} <= claude)
        self.assertTrue({"claude-as-advisor-guardrail", "claude-as-critic-guardrail", "cursor-as-advisor-guardrail", "cursor-as-critic-guardrail"} <= codex)
        self.assertTrue({"claude-as-advisor-guardrail", "claude-as-critic-guardrail", "codex-as-advisor-guardrail", "codex-as-critic-guardrail"} <= cursor)

    def test_provider_plugins_have_only_required_consumer_manifests(self):
        expected = {
            "codex-as-advisor-guardrail": (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json"),
            "claude-as-advisor-guardrail": (".codex-plugin/plugin.json", ".cursor-plugin/plugin.json"),
            "claude-as-critic-guardrail": (".codex-plugin/plugin.json", ".cursor-plugin/plugin.json"),
            "cursor-as-advisor-guardrail": (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"),
            "cursor-as-critic-guardrail": (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"),
        }
        for plugin, manifests in expected.items():
            for manifest in manifests:
                data = json.loads((ROOT / "plugins" / plugin / manifest).read_text(encoding="utf-8"))
                self.assertEqual(data["name"], plugin)

    def test_every_catalog_source_resolves_to_matching_host_manifest(self):
        catalogs = (
            (".claude-plugin/marketplace.json", ".claude-plugin/plugin.json"),
            (".agents/plugins/marketplace.json", ".codex-plugin/plugin.json"),
            (".cursor-plugin/marketplace.json", ".cursor-plugin/plugin.json"),
        )
        for relative, manifest_relative in catalogs:
            catalog = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            for entry in catalog["plugins"]:
                source = entry["source"]
                source_path = source["path"] if isinstance(source, dict) else source
                plugin = (ROOT / source_path).resolve()
                self.assertTrue(plugin.is_dir(), f"missing catalog source: {plugin}")
                manifest = plugin / manifest_relative
                self.assertTrue(manifest.is_file(), f"missing host manifest: {manifest}")
                self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["name"], entry["name"])


class AdapterContractTests(unittest.TestCase):
    NEW = {
        "codex-as-advisor-guardrail": ("advisor_server.py", "consult_advisor"),
        "claude-as-advisor-guardrail": ("advisor_server.py", "consult_advisor"),
        "claude-as-critic-guardrail": ("critic_server.py", "consult_critic"),
    }

    def handshake(self, plugin: str, server: str) -> list[dict]:
        request = b"".join(json.dumps(message).encode("utf-8") + b"\n" for message in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"},
        ))
        completed = subprocess.run(
            [sys.executable, str(ROOT / "plugins" / plugin / "mcp" / server)],
            input=request, capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        return [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line]

    def test_new_mcp_servers_complete_real_stdio_handshakes(self):
        for plugin, (server, tool) in self.NEW.items():
            replies = self.handshake(plugin, server)
            self.assertEqual([reply["id"] for reply in replies], [1, 2, 3])
            self.assertEqual(replies[1]["result"]["tools"][0]["name"], tool)

    def test_claude_provider_uses_latest_opus_alias_at_high_effort_read_only(self):
        for plugin, server in (("claude-as-advisor-guardrail", "advisor_server.py"), ("claude-as-critic-guardrail", "critic_server.py")):
            source = (ROOT / "plugins" / plugin / "mcp" / server).read_text(encoding="utf-8")
            self.assertIn('MODEL = "opus"', source)
            for flag in ('"--effort", "high"', '"--permission-mode", "plan"', '"--safe-mode"', '"Read,Grep,Glob"'):
                self.assertIn(flag, source)

    def test_codex_advisor_is_sol_high_and_read_only(self):
        source = (ROOT / "plugins/codex-as-advisor-guardrail/mcp/advisor_server.py").read_text(encoding="utf-8")
        self.assertIn('MODEL = "gpt-5.6-sol"', source)
        self.assertIn('model_reasoning_effort="high"', source)
        self.assertIn('"--sandbox", "read-only"', source)

    def test_cursor_adapters_are_rooted_native_and_fail_open(self):
        plugins = tuple(self.NEW) + ("cursor-as-advisor-guardrail", "cursor-as-critic-guardrail")
        for plugin in plugins:
            mcp = json.loads((ROOT / "plugins" / plugin / "mcp.json").read_text(encoding="utf-8"))
            server = next(iter(mcp["mcpServers"].values()))
            self.assertEqual(server["cwd"], "${PLUGIN_ROOT}")
            self.assertTrue(any("${PLUGIN_ROOT}/mcp/" in arg for arg in server["args"]))
            hooks = json.loads((ROOT / "plugins" / plugin / "hooks/cursor-hooks.json").read_text(encoding="utf-8"))["hooks"]
            gate = hooks["preToolUse"][0]
            for tool in ("Write", "StrReplace", "Delete"):
                self.assertIn(tool, gate["matcher"])
            self.assertFalse(gate["failClosed"])
            self.assertIn("afterMCPExecution", hooks)

    def test_codex_adapters_bundle_mcp_and_hooks(self):
        for plugin in ("claude-as-advisor-guardrail", "claude-as-critic-guardrail", "cursor-as-advisor-guardrail", "cursor-as-critic-guardrail"):
            manifest = json.loads((ROOT / "plugins" / plugin / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
            self.assertIn("mcpServers", manifest)
            hooks = json.loads((ROOT / "plugins" / plugin / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
            self.assertIn("PreToolUse", hooks)
            self.assertIn("PostToolUse", hooks)
            self.assertIn("SessionStart", hooks)

    def test_new_cursor_gates_fail_open_when_matching_mcp_is_absent(self):
        cases = (
            ("codex-as-advisor-guardrail", "advisor_gate.py"),
            ("claude-as-advisor-guardrail", "advisor_gate.py"),
            ("claude-as-critic-guardrail", "critic_gate.py"),
        )
        payload = json.dumps({
            "conversation_id": "matrix-smoke",
            "hook_event_name": "preToolUse",
            "tool_name": "StrReplace",
            "workspace_roots": [str(ROOT)],
        })
        for plugin, gate in cases:
            hooks = ROOT / "plugins" / plugin / "hooks"
            completed = subprocess.run(
                [sys.executable, str(hooks / gate)], input=payload,
                capture_output=True, encoding="utf-8", cwd=hooks,
                timeout=60, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["permission"], "allow")
            self.assertIn("has not registered", completed.stderr)

    def test_new_session_start_hooks_inject_role_protocols(self):
        cases = (
            ("codex-as-advisor-guardrail", "advisor_context.py", "Codex Advisor Protocol"),
            ("claude-as-advisor-guardrail", "advisor_context.py", "Claude Advisor Protocol"),
            ("claude-as-critic-guardrail", "critic_context.py", "Claude Critic Protocol"),
        )
        for plugin, context_script, title in cases:
            hooks = ROOT / "plugins" / plugin / "hooks"
            completed = subprocess.run(
                [sys.executable, str(hooks / context_script)],
                input=json.dumps({"hook_event_name": "sessionStart"}),
                capture_output=True, encoding="utf-8", cwd=hooks,
                timeout=60, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(title, json.loads(completed.stdout)["additional_context"])

    def assert_live_server_arms_gate(self, plugin: str, server: str, gate: str, host: str) -> None:
        plugin_root = ROOT / "plugins" / plugin
        environment = {**os.environ, "AGENTIC_RAILS_MCP_HOST": host}
        if host == "cursor":
            environment["AGENTIC_RAILS_WORKSPACE"] = str(ROOT)
        process = subprocess.Popen(
            [sys.executable, str(plugin_root / "mcp" / server)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=ROOT, env=environment,
        )
        try:
            for message in (
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ):
                process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            self.assertEqual(json.loads(process.stdout.readline())["id"], 1)
            self.assertEqual(json.loads(process.stdout.readline())["id"], 2)

            cursor = host == "cursor"
            payload = {
                "conversation_id" if cursor else "session_id": f"live-{plugin}-{host}",
                "hook_event_name": "preToolUse" if cursor else "PreToolUse",
                "tool_name": "StrReplace" if cursor else "apply_patch",
                "cwd": str(ROOT),
            }
            if cursor:
                payload["workspace_roots"] = [str(ROOT)]
            gate_environment = {**os.environ}
            if not cursor:
                gate_environment["PLUGIN_ROOT"] = str(plugin_root)
            completed = subprocess.run(
                [sys.executable, str(plugin_root / "hooks" / gate)],
                input=json.dumps(payload), capture_output=True, encoding="utf-8",
                cwd=plugin_root / "hooks", env=gate_environment,
                timeout=60, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            decision = json.loads(completed.stdout)
            if cursor:
                self.assertEqual(decision["permission"], "deny")
            else:
                self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
        finally:
            if process.stdin:
                process.stdin.close()
            process.wait(timeout=60)
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

    def test_live_mcp_registration_arms_cursor_gates(self):
        for plugin, server, gate in (
            ("codex-as-advisor-guardrail", "advisor_server.py", "advisor_gate.py"),
            ("claude-as-advisor-guardrail", "advisor_server.py", "advisor_gate.py"),
            ("claude-as-critic-guardrail", "critic_server.py", "critic_gate.py"),
        ):
            self.assert_live_server_arms_gate(plugin, server, gate, "cursor")

    def test_live_mcp_registration_arms_codex_gates(self):
        for plugin, server, gate in (
            ("claude-as-advisor-guardrail", "advisor_server.py", "advisor_gate.py"),
            ("claude-as-critic-guardrail", "critic_server.py", "critic_gate.py"),
            ("cursor-as-advisor-guardrail", "advisor_server.py", "advisor_gate.py"),
            ("cursor-as-critic-guardrail", "critic_server.py", "critic_gate.py"),
        ):
            self.assert_live_server_arms_gate(plugin, server, gate, "codex")


if __name__ == "__main__":
    unittest.main()
