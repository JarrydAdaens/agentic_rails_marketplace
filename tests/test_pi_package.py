# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.
"""Structural tests for the pi package in this repository.

Pi distributes through packages: one repository-root ``package.json``
declaring a ``pi.extensions`` glob over the extension sources. This is
structurally unlike the other three hosts (no catalog, no per-plugin host
manifest, no ``.pi-plugin`` folders), so it is not part of the host matrix in
``test_cross_ide_guardrails.py``.

Behavioral tests for the TypeScript modules live beside each module and run
under pi's bundled Node (see ``run_pi_behavior_tests.py``); this file checks
the package shape only.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
PI_ROOT = ROOT / "plugins" / "pi"
EXTENSION_GLOB = "plugins/pi/*/extensions/*.ts"
# Host manifest directories the other three hosts use; none may appear under
# plugins/pi/ because pi has no manifest concept.
FORBIDDEN_HOST_DIRS = {".claude-plugin", ".codex-plugin", ".cursor-plugin"}


class PiPackageManifestTests(unittest.TestCase):
    """The repository root carries the one pi package manifest, in the plan's shape."""

    def test_root_package_json_exists_and_is_valid_json(self):
        manifest_path = ROOT / "package.json"
        self.assertTrue(manifest_path.is_file(), "missing repository-root package.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIsInstance(manifest, dict)

    def test_root_package_json_declares_the_pi_package(self):
        manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("name"), "agentic-rails-pi")
        self.assertTrue(manifest.get("private"), "the pi package is never published")
        self.assertIn("pi-package", manifest.get("keywords", []))
        self.assertEqual(manifest.get("pi"), {"extensions": [EXTENSION_GLOB]})
        self.assertEqual(
            manifest.get("peerDependencies"),
            {"@earendil-works/pi-coding-agent": "*", "typebox": "*"},
        )


class PiExtensionGlobTests(unittest.TestCase):
    """The extension glob resolves to real files, and shared/ stays out of it."""

    def test_extension_glob_resolves_to_real_files(self):
        matches = sorted(PI_ROOT.parent.parent.glob(EXTENSION_GLOB))
        self.assertTrue(matches, f"no extension files matched {EXTENSION_GLOB!r}")
        for match in matches:
            self.assertTrue(match.is_file(), f"glob matched a non-file: {match}")
            self.assertTrue(match.suffix == ".ts", f"glob matched a non-TypeScript file: {match}")

    def test_shared_is_not_matched_by_the_extension_glob(self):
        # shared/ is imported by the extensions but must never be loaded as
        # one itself; the glob's /extensions/ segment is what keeps it out.
        for match in ROOT.glob(EXTENSION_GLOB):
            self.assertNotIn(
                PI_ROOT / "shared",
                match.parents,
                f"the extension glob matched inside plugins/pi/shared/: {match}",
            )


class PiGuardrailFolderTests(unittest.TestCase):
    """Every guardrail folder is a proper pi guardrail folder."""

    def test_every_guardrail_folder_has_extensions_and_readme(self):
        # shared/ is the one deliberate exception: it is a library imported by
        # the extensions, not a guardrail, and carries no extensions/ folder.
        guardrails = [d for d in PI_ROOT.iterdir() if d.is_dir() and d.name != "shared"]
        self.assertTrue(guardrails, "expected at least one guardrail folder under plugins/pi/")
        for guardrail in guardrails:
            self.assertTrue(
                (guardrail / "extensions").is_dir(),
                f"{guardrail} is missing its extensions/ folder",
            )
            self.assertTrue(
                (guardrail / "README.md").is_file(),
                f"{guardrail} is missing its README.md",
            )


class PiHostIsolationTests(unittest.TestCase):
    """Pi has no per-plugin host manifests; none may leak into its tree."""

    def test_no_foreign_host_manifest_dirs_under_plugins_pi(self):
        for path in PI_ROOT.rglob("*"):
            self.assertNotIn(
                path.name,
                FORBIDDEN_HOST_DIRS,
                f"a {path.name} directory exists under plugins/pi/: {path}",
            )


if __name__ == "__main__":
    unittest.main()
