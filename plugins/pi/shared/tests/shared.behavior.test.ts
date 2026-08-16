// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Behavioral tests for the shared pi guardrail modules (bash-segments,
 * harness-config, budget). Pure-logic tests run directly under pi's bundled
 * Node via native type stripping.
 */

import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { basename, leadingExecutable, splitSegments } from "../bash-segments.ts";
import { capToBudget, TRUNCATION_MARKER } from "../budget.ts";
import { isEnabled, loadHarnessConfig } from "../harness-config.ts";

let failed = 0;
let passed = 0;

function check(label: string, fn: () => void) {
	try {
		fn();
		passed++;
		console.log(`  ok   ${label}`);
	} catch (err) {
		failed++;
		console.error(`  FAIL ${label} — ${err instanceof Error ? err.message : String(err)}`);
	}
}

// --- splitSegments ---------------------------------------------------------

check("splitSegments: pipes", () =>
	assert.deepEqual(splitSegments("cat x | python"), ["cat x ", " python"]));
check("splitSegments: chains and semicolons", () =>
	assert.deepEqual(splitSegments("a && b ; c || d"), ["a ", " b ", " c ", " d"]));
check("splitSegments: newlines and parens", () =>
	assert.deepEqual(splitSegments("(cd x)\ny"), ["", "cd x", "", "y"]));

// --- leadingExecutable -----------------------------------------------------

check("leadingExecutable: plain", () =>
	assert.equal(leadingExecutable("python --version"), "python"));
check("leadingExecutable: skips sudo", () =>
	assert.equal(leadingExecutable("sudo python x.py"), "python"));
check("leadingExecutable: skips env wrapper and its args", () =>
	assert.equal(leadingExecutable("env FOO=bar python"), "python"));
check("leadingExecutable: skips inline assignments", () =>
	assert.equal(leadingExecutable("FOO=1 python x.py"), "python"));
check("leadingExecutable: skips stacked wrappers", () =>
	assert.equal(leadingExecutable("nice command python"), "python"));
check("leadingExecutable: only wrappers resolves to null", () =>
	assert.equal(leadingExecutable("sudo env time"), null));
check("leadingExecutable: empty segment is null", () =>
	assert.equal(leadingExecutable("   "), null));

// --- basename ----------------------------------------------------------------

check("basename: posix path", () =>
	assert.equal(basename("/usr/bin/python3.12"), "python3.12"));
check("basename: windows path + .exe", () =>
	assert.equal(basename("C:\\Python314\\python.exe"), "python"));
check("basename: .EXE is case-insensitive", () =>
	assert.equal(basename("C:/Python314/python.EXE"), "python"));
check("basename: bare name unchanged", () =>
	assert.equal(basename("uv"), "uv"));

// --- budget ------------------------------------------------------------------

check("budget: under the cap is unchanged", () =>
	assert.equal(capToBudget("hello", 10), "hello"));
check("budget: at the cap is unchanged", () =>
	assert.equal(capToBudget("hello", 5), "hello"));
check("budget: over the cap is cut to exactly the cap with the marker", () => {
	const out = capToBudget("hello world, this is a test", 20);
	assert.equal(out.length, 20);
	assert.ok(out.endsWith(TRUNCATION_MARKER));
});
check("budget: cap smaller than the marker degrades to a plain cut", () => {
	const out = capToBudget("hello world", 3);
	assert.equal(out, "hel");
});
check("budget: non-positive cap yields the empty string", () =>
	assert.equal(capToBudget("hello", 0), ""));
check("budget: deterministic", () =>
	assert.equal(capToBudget("abcde", 7), capToBudget("abcde", 7)));

// --- harness-config -----------------------------------------------------------

const root = mkdtempSync(join(tmpdir(), "pi-guardrail-harness-test-"));

check("harness-config: absent config is null (enforce with defaults)", () => {
	assert.equal(loadHarnessConfig(root, "python-uv-guardrail"), null);
	assert.equal(isEnabled(loadHarnessConfig(root, "python-uv-guardrail")), true);
});

const dir = join(root, "harness", "python-uv-guardrail");
mkdirSync(dir, { recursive: true });

check("harness-config: empty config is null (enforce with defaults)", () => {
	writeFileSync(join(dir, "config.json"), "   \n");
	assert.equal(loadHarnessConfig(root, "python-uv-guardrail"), null);
});

check("harness-config: malformed config is null (enforce with defaults)", () => {
	writeFileSync(join(dir, "config.json"), "{not json");
	assert.equal(loadHarnessConfig(root, "python-uv-guardrail"), null);
});

check("harness-config: non-object config is null (enforce with defaults)", () => {
	writeFileSync(join(dir, "config.json"), "[1, 2, 3]");
	assert.equal(loadHarnessConfig(root, "python-uv-guardrail"), null);
});

check("harness-config: enabled:false is honored", () => {
	writeFileSync(join(dir, "config.json"), JSON.stringify({ enabled: false }));
	assert.equal(isEnabled(loadHarnessConfig(root, "python-uv-guardrail")), false);
});

check("harness-config: enabled:true and extra keys pass through", () => {
	writeFileSync(
		join(dir, "config.json"),
		JSON.stringify({ enabled: true, blockedPattern: "^python$", allowCommands: ["ok"] }),
	);
	const config = loadHarnessConfig(root, "python-uv-guardrail");
	assert.equal(isEnabled(config), true);
	assert.equal(config?.blockedPattern, "^python$");
});

console.log(`\nshared behavior: ${passed} passed, ${failed} failed`);
if (failed > 0) {
	process.exitCode = 1;
}
