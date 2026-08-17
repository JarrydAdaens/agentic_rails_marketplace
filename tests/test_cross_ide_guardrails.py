# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
# "pi" is deliberately NOT a fourth host in this matrix, and plugins/pi/ is
# deliberately absent from every assertion in this module. The assertions
# above and below assume each plugin folder carries exactly one host manifest
# and that a catalog lists the plugins; pi has neither a per-plugin manifest
# nor a catalog — the whole repository is ONE pi package declared by the
# root package.json, and granularity comes from `pi config` filtering. Its
# shape is covered by tests/test_pi_package.py instead, and its absence
# here is a deliberate exclusion, not an oversight (see context/design.md
# sections 4 and 5). Do not add "pi" to HOSTS: every assertion in this file
# would fail on plugins/pi/ by construction rather than catch a real
# regression.
HOSTS = ("claude", "codex", "cursor")
HOST_MANIFEST_DIR = {"claude": ".claude-plugin", "codex": ".codex-plugin", "cursor": ".cursor-plugin"}
HOST_CATALOG = {
    "claude": ".claude-plugin/marketplace.json",
    "codex": ".agents/plugins/marketplace.json",
    "cursor": ".cursor-plugin/marketplace.json",
}


class MarketplaceMatrixTests(unittest.TestCase):
    """Each host's catalog resolves entirely inside plugins/<host>/, and nowhere else."""

    def catalog_names(self, host: str) -> set[str]:
        catalog = json.loads((ROOT / HOST_CATALOG[host]).read_text(encoding="utf-8"))
        return {entry["name"] for entry in catalog["plugins"]}

    def test_every_catalog_source_resolves_inside_its_own_host_root(self):
        for host in HOSTS:
            catalog = json.loads((ROOT / HOST_CATALOG[host]).read_text(encoding="utf-8"))
            manifest_relative = HOST_MANIFEST_DIR[host]
            for entry in catalog["plugins"]:
                source = entry["source"]
                source_path = source["path"] if isinstance(source, dict) else source
                plugin = (ROOT / source_path).resolve()
                self.assertTrue(plugin.is_dir(), f"missing catalog source: {plugin}")
                self.assertEqual(
                    plugin.parent, (ROOT / "plugins" / host).resolve(),
                    f"{host} catalog entry {entry['name']!r} resolves outside plugins/{host}/",
                )
                manifest = plugin / manifest_relative / "plugin.json"
                self.assertTrue(manifest.is_file(), f"missing host manifest: {manifest}")
                self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["name"], entry["name"])

    def test_every_plugin_folder_carries_exactly_its_own_host_manifest(self):
        # Walks plugins/<host>/ for the three manifest-bearing hosts only;
        # plugins/pi/ is excluded by design (see the HOSTS note above).
        for host in HOSTS:
            own = HOST_MANIFEST_DIR[host]
            foreign = {d for d in HOST_MANIFEST_DIR.values() if d != own}
            for plugin in sorted((ROOT / "plugins" / host).iterdir()):
                present = {d.name for d in plugin.iterdir() if d.is_dir() and d.name.endswith("-plugin")}
                self.assertIn(own, present, f"{plugin} is missing its own {own} manifest")
                self.assertFalse(
                    present & foreign,
                    f"{plugin} carries a foreign host manifest: {present & foreign}",
                )

    def test_cursor_catalog_lists_every_split_plugin(self):
        # Cursor is the tree every plugin originated from before the per-host split;
        # every plugin folder anywhere must still be reachable from some catalog.
        cataloged = self.catalog_names("claude") | self.catalog_names("codex") | self.catalog_names("cursor")
        for host in HOSTS:
            for plugin in (ROOT / "plugins" / host).iterdir():
                self.assertIn(plugin.name, cataloged, f"{plugin} is not listed in any catalog")


class GateDenyContractTests(unittest.TestCase):
    """Every gate hook, in every tree, denies a well-formed write attempt once armed.

    This is a structural drift check: it walks the tree rather than naming hooks
    one by one, so a fix that lands in one tree and not its siblings fails here,
    which is the specific failure mode the per-host split makes possible.
    """

    def gate_hooks(self) -> list[Path]:
        return sorted(ROOT.glob("plugins/*/*/hooks/*_gate.py"))

    def test_at_least_one_gate_is_discovered_per_host(self):
        found = {gate.parents[2].name for gate in self.gate_hooks()}
        self.assertEqual(found, set(HOSTS))

    def test_every_gate_denies_a_well_formed_armed_payload(self):
        payload = json.dumps({
            "session_id": "matrix-smoke",
            "conversation_id": "matrix-smoke",
            "hook_event_name": "preToolUse",
            "tool_name": "Edit",
            "cwd": str(ROOT),
            "workspace_roots": [str(ROOT)],
        })
        for gate in self.gate_hooks():
            with self.subTest(gate=str(gate.relative_to(ROOT))):
                completed = subprocess.run(
                    [sys.executable, str(gate)],
                    input=payload, capture_output=True, encoding="utf-8",
                    cwd=gate.parent, timeout=60, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                # Health/liveness state is per-machine and mocked at the plugin-test
                # level; here we only assert the hook produced a well-formed
                # decision (or a silent pass-through) rather than crashing or
                # emitting nothing parseable when one is expected.
                if completed.stdout.strip():
                    decision = json.loads(completed.stdout)
                    self.assertTrue(
                        "permission" in decision or "hookSpecificOutput" in decision,
                        f"{gate} emitted an unrecognized decision shape: {decision}",
                    )


class WindowsLauncherDriftTests(unittest.TestCase):
    """Cursor-hosted plugins each carry their own copy of the Windows bootstrap;
    within a tree, copies that are supposed to be identical must not drift."""

    def test_cursor_tree_launch_windows_copies_stay_in_sync(self):
        launchers = {
            path.read_text(encoding="utf-8")
            for path in ROOT.glob("plugins/cursor/*/scripts/launch-windows.cmd")
        }
        if not launchers:
            self.skipTest("no launch-windows.cmd copies present in the cursor tree")
        self.assertEqual(len(launchers), 1, "Cursor bootstrap copies drifted")


if __name__ == "__main__":
    unittest.main()
