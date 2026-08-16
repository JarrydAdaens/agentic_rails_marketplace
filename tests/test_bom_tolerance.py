# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.

"""Every gate hook must survive a BOM-prefixed payload, in every plugin.

Cursor's Windows CLI prefixes the JSON it pipes to a hook over stdin with a
UTF-8 BOM. `json.loads` and `ConvertFrom-Json` both reject it, and because a
gate fails open when it cannot parse its payload, one BOM silently disarmed
every write gate in this marketplace while all of them still reported healthy.

This suite walks the plugin tree rather than naming hooks one by one, so a hook
added later -- or a copy of an existing hook that drifts after the per-host
split -- is covered without anyone remembering to add it here. That matters more
than the individual assertions: the original defect survived because one fix
landed in some copies and not others.

The assertion is deliberately narrow and state-free. A gate's actual decision
depends on session markers and advisor health, which differ per plugin and per
machine, so this checks only the thing that is universally true: given a
*well-formed* payload, no hook may report a parse failure. Deny/allow behavior
is asserted in each plugin's own suite, where the state can be controlled.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
PLUGINS = ROOT / "plugins"

BOM = b"\xef\xbb\xbf"

# Phrases the hooks print when they cannot understand stdin. Seeing one of these
# for a well-formed payload means the BOM defeated the parser again.
PARSE_FAILURE_MARKERS = (
    "invalid JSON",
    "could not read stdin",
    "could not parse",
    "expected an object",
)

# A payload shaped like a Cursor preToolUse write attempt. Every gate reads some
# subset of these keys; none should choke on the extras.
PAYLOAD = {
    "hook_event_name": "preToolUse",
    "conversation_id": "bom-tolerance-probe",
    "session_id": "bom-tolerance-probe",
    "tool_name": "Write",
    "tool_input": {"file_path": "probe.txt", "content": "hello"},
    "cwd": str(ROOT),
    "workspace_roots": [str(ROOT)],
}

PYTHON_RUNNER = (
    "import os,sys,runpy;"
    "d=sys.argv[1];"
    "sys.path.insert(0,d);"
    "runpy.run_path(os.path.join(d,sys.argv[2]),run_name='__main__')"
)


def python_gates() -> list[Path]:
    """Gate hooks that read a payload from stdin and emit a decision.

    Context hooks are excluded on purpose: they run a live health probe that can
    spawn a vendor CLI, which is not something a unit suite should trigger.
    """
    found = sorted(PLUGINS.glob("*/*/hooks/*_gate.py"))
    fence_candidates = PLUGINS.glob("*/claude-home-fence-guardrail/hooks/claude_home_fence.py")
    found.extend(sorted(fence_candidates))
    return found


def powershell_gates() -> list[Path]:
    names = ("enforce-uv-python.ps1", "block-readme-write.ps1", "block-readme-git.ps1")
    return sorted(p for p in PLUGINS.glob("*/*/hooks/*.ps1") if p.name in names)


class BomToleranceTests(unittest.TestCase):
    def assert_no_parse_failure(self, label: str, stderr: str) -> None:
        for marker in PARSE_FAILURE_MARKERS:
            if marker in stderr:
                self.fail(
                    f"{label} failed to parse a BOM-prefixed payload and fell back to "
                    f"fail-open.\nstderr: {stderr.strip()}"
                )

    def test_at_least_one_gate_of_each_kind_is_discovered(self):
        # Guards against the walk silently matching nothing after a refactor,
        # which would turn this whole suite into a green no-op.
        self.assertTrue(python_gates(), "no Python gate hooks discovered under plugins/")
        self.assertTrue(powershell_gates(), "no PowerShell gate hooks discovered under plugins/")

    def test_python_gates_parse_bom_prefixed_payload(self):
        body = BOM + json.dumps(PAYLOAD).encode("utf-8")
        for gate in python_gates():
            with self.subTest(gate=str(gate.relative_to(PLUGINS))):
                result = subprocess.run(
                    [sys.executable, "-c", PYTHON_RUNNER, str(gate.parent), gate.name],
                    input=body,
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
                stderr = result.stderr.decode("utf-8", errors="replace")
                self.assert_no_parse_failure(str(gate.relative_to(PLUGINS)), stderr)

    def test_python_gates_report_genuinely_malformed_input(self):
        # The mirror of the above: a hook that stays silent on real garbage is
        # back to failing open invisibly, which is what hid the original defect.
        body = BOM + b"{not json at all"
        noisy = 0
        for gate in python_gates():
            result = subprocess.run(
                [sys.executable, "-c", PYTHON_RUNNER, str(gate.parent), gate.name],
                input=body,
                capture_output=True,
                timeout=60,
                check=False,
            )
            stderr = result.stderr.decode("utf-8", errors="replace")
            if any(marker in stderr for marker in PARSE_FAILURE_MARKERS):
                noisy += 1
        self.assertEqual(
            noisy,
            len(python_gates()),
            "every Python gate must say so on stderr when it cannot parse stdin",
        )

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh not available")
    def test_powershell_gates_parse_bom_prefixed_payload(self):
        body = BOM + json.dumps(PAYLOAD).encode("utf-8")
        for gate in powershell_gates():
            with self.subTest(gate=str(gate.relative_to(PLUGINS))):
                result = subprocess.run(
                    ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(gate)],
                    input=body,
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
                stderr = result.stderr.decode("utf-8", errors="replace")
                self.assert_no_parse_failure(str(gate.relative_to(PLUGINS)), stderr)

    def test_no_hook_writes_a_bom_to_stdout(self):
        # utf-8-sig strips a BOM when decoding but emits one when encoding. If it
        # were ever applied to stdout, the decision JSON a host reads back would
        # itself start with a BOM and fail to parse on the other side.
        body = BOM + json.dumps(PAYLOAD).encode("utf-8")
        for gate in python_gates():
            with self.subTest(gate=str(gate.relative_to(PLUGINS))):
                result = subprocess.run(
                    [sys.executable, "-c", PYTHON_RUNNER, str(gate.parent), gate.name],
                    input=body,
                    capture_output=True,
                    timeout=60,
                    check=False,
                )
                self.assertFalse(
                    result.stdout.startswith(BOM),
                    f"{gate.relative_to(PLUGINS)} emitted a BOM on stdout",
                )


if __name__ == "__main__":
    unittest.main()
