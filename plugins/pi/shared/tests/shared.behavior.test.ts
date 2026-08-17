// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Behavioral tests for the shared pi guardrail modules (bash-segments,
 * harness-config, budget, cli-resolution, run-external, advisor-failure). Pure-logic tests
 * run directly under pi's bundled Node via native type stripping;
 * run-external is exercised against trivial node subprocesses (never the
 * claude CLI, no mock framework).
 */

import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { basename, leadingExecutable, splitSegments } from "../bash-segments.ts";
import { capToBudget, TRUNCATION_MARKER } from "../budget.ts";
import { isEnabled, loadHarnessConfig } from "../harness-config.ts";
import { isBatchShim, knownCandidates, resolveCli, searchPath } from "../cli-resolution.ts";
import { DEFAULT_TIMEOUT_SECONDS, runExternal } from "../run-external.ts";
import { classifyAdvisorFailure, hardFailureCategory, HARD_FAILURE_HINTS } from "../advisor-failure.ts";

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

// --- cli-resolution ------------------------------------------------------------

check("cli-resolution: isBatchShim classifies shims", () => {
	assert.equal(isBatchShim("C:\\x\\claude.cmd"), true);
	assert.equal(isBatchShim("C:\\x\\agent.BAT"), true);
	assert.equal(isBatchShim("C:\\x\\codex.exe"), false);
	assert.equal(isBatchShim("claude"), false);
});

// A fake machine: shims and executables in the usual per-vendor locations,
// a SystemRoot with cmd.exe, and a PATH directory as fallback.
const cliRoot = mkdtempSync(join(tmpdir(), "pi-cli-resolution-"));
const fakeLocal = join(cliRoot, "local");
const fakeRoaming = join(cliRoot, "roaming");
const fakeProfile = join(cliRoot, "profile");
const fakeSys = join(cliRoot, "sys");
const pathDir = join(cliRoot, "pathdir");

mkdirSync(join(fakeLocal, "pnpm"), { recursive: true });
writeFileSync(join(fakeLocal, "pnpm", "claude.cmd"), "@echo off");
mkdirSync(join(fakeLocal, "Programs", "OpenAI", "Codex", "bin"), { recursive: true });
writeFileSync(join(fakeLocal, "Programs", "OpenAI", "Codex", "bin", "codex.exe"), "x");
mkdirSync(join(fakeLocal, "cursor-agent"), { recursive: true });
writeFileSync(join(fakeLocal, "cursor-agent", "agent.cmd"), "@echo off");
mkdirSync(join(fakeRoaming, "npm"), { recursive: true });
writeFileSync(join(fakeRoaming, "npm", "codex.cmd"), "@echo off");
mkdirSync(join(fakeProfile, ".claude", "local"), { recursive: true });
writeFileSync(join(fakeProfile, ".claude", "local", "claude.exe"), "x");
mkdirSync(join(fakeSys, "System32"), { recursive: true });
writeFileSync(join(fakeSys, "System32", "cmd.exe"), "x");
mkdirSync(pathDir, { recursive: true });
writeFileSync(join(pathDir, "claude.cmd"), "@echo off");

const fakeEnv = {
	LOCALAPPDATA: fakeLocal,
	APPDATA: fakeRoaming,
	USERPROFILE: fakeProfile,
	SystemRoot: fakeSys,
	PATH: pathDir,
};
const cmdExe = join(fakeSys, "System32", "cmd.exe");

check("cli-resolution: knownCandidates lists the vendored locations", () => {
	assert.deepEqual(knownCandidates("codex", fakeEnv), [
		join(fakeLocal, "Programs", "OpenAI", "Codex", "bin", "codex.exe"),
		join(fakeLocal, "OpenAI", "Codex", "bin", "codex.exe"),
		join(fakeRoaming, "npm", "codex.cmd"),
	]);
	assert.deepEqual(knownCandidates("agent", fakeEnv), [
		join(fakeLocal, "cursor-agent", "agent.cmd"),
		join(fakeLocal, "cursor-agent", "agent.exe"),
	]);
	assert.deepEqual(knownCandidates("some-other-cli", fakeEnv), []);
});

check("cli-resolution: claude .cmd shim is wrapped in cmd.exe /d /c", () => {
	const r = resolveCli("claude", fakeEnv);
	const shim = join(fakeLocal, "pnpm", "claude.cmd");
	assert.equal(r.found, true);
	assert.equal(r.path, shim);
	assert.deepEqual(r.argvPrefix, [cmdExe, "/d", "/c", shim]);
});

check("cli-resolution: cursor agent .cmd shim is wrapped in cmd.exe /d /c", () => {
	const r = resolveCli("agent", fakeEnv);
	const shim = join(fakeLocal, "cursor-agent", "agent.cmd");
	assert.equal(r.found, true);
	assert.deepEqual(r.argvPrefix, [cmdExe, "/d", "/c", shim]);
});

check("cli-resolution: codex .exe is a direct argv prefix", () => {
	const r = resolveCli("codex", fakeEnv);
	const exe = join(fakeLocal, "Programs", "OpenAI", "Codex", "bin", "codex.exe");
	assert.equal(r.found, true);
	assert.deepEqual(r.argvPrefix, [exe]);
});

check("cli-resolution: PATH fallback finds the CLI", () => {
	const r = resolveCli("claude", { SystemRoot: fakeSys, PATH: pathDir });
	assert.equal(r.found, true);
	assert.equal(r.path, join(pathDir, "claude.cmd"));
	assert.deepEqual(r.argvPrefix, [cmdExe, "/d", "/c", join(pathDir, "claude.cmd")]);
});

check("cli-resolution: missing CLI is a returned not-found, never a throw", () => {
	const r = resolveCli("claude", { PATH: join(cliRoot, "nowhere") });
	assert.equal(r.found, false);
	assert.equal(typeof r.note, "string");
	assert.ok((r.note ?? "").includes("claude"));
});

check("cli-resolution: a shim without cmd.exe is not found, not a broken argv", () => {
	const r = resolveCli("claude", { ...fakeEnv, SystemRoot: join(cliRoot, "no-such-root") });
	assert.equal(r.found, false);
	assert.ok((r.note ?? "").includes("cmd.exe"));
});

check("cli-resolution: searchPath is null without a PATH", () => {
	assert.equal(searchPath("claude", {}), null);
});

// --- run-external ----------------------------------------------------------------
//
// These drive real, trivial node subprocesses (this very runtime) to prove
// the spawn contract — prompt on stdin, status mapping, timeout, abort,
// budget. They do not touch the claude CLI and build no mock framework.

const NODE = process.execPath;

async function checkAsync(label: string, fn: () => Promise<void>) {
	try {
		await fn();
		passed++;
		console.log(`  ok   ${label}`);
	} catch (err) {
		failed++;
		console.error(`  FAIL ${label} — ${err instanceof Error ? err.message : String(err)}`);
	}
}

await checkAsync("run-external: ok — prompt arrives on stdin, stdout is captured", async () => {
	const script =
		"let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>process.stdout.write('got:'+s));";
	const r = await runExternal([NODE, "-e", script], "ping", { timeoutSeconds: 15 });
	assert.equal(r.status, "ok");
	assert.equal(r.exitCode, 0);
	assert.equal(r.stdout, "got:ping");
});

await checkAsync("run-external: non-zero exit is a returned failure with stderr", async () => {
	const r = await runExternal(
		[NODE, "-e", "process.stderr.write('nope');process.exitCode=3;"],
		"hi",
		{ timeoutSeconds: 15 },
	);
	assert.equal(r.status, "failed");
	assert.equal(r.exitCode, 3);
	assert.equal(r.stderr, "nope");
});

await checkAsync("run-external: timeout is a returned timedout, not a throw", async () => {
	const r = await runExternal([NODE, "-e", "setTimeout(()=>{},5000);"], "hi", { timeoutSeconds: 1 });
	assert.equal(r.status, "timedout");
	assert.ok((r.note ?? "").includes("timed out"));
});

await checkAsync("run-external: an AbortSignal cancels the call", async () => {
	const controller = new AbortController();
	const killer = setTimeout(() => controller.abort(), 100);
	try {
		const r = await runExternal([NODE, "-e", "setTimeout(()=>{},5000);"], "hi", {
			timeoutSeconds: 30,
			signal: controller.signal,
		});
		assert.equal(r.status, "failed");
		assert.ok((r.note ?? "").includes("aborted"));
	} finally {
		clearTimeout(killer);
	}
});

await checkAsync("run-external: an already-aborted signal fails fast", async () => {
	const controller = new AbortController();
	controller.abort();
	const r = await runExternal([NODE, "-e", "setTimeout(()=>{},5000);"], "hi", {
		timeoutSeconds: 30,
		signal: controller.signal,
	});
	assert.equal(r.status, "failed");
});

await checkAsync("run-external: a missing CLI is a returned failure, never a throw", async () => {
	const r = await runExternal([join(cliRoot, "definitely-not-here.exe"), "--x"], "hi", { timeoutSeconds: 10 });
	assert.equal(r.status, "failed");
	assert.ok((r.note ?? "").includes("Could not start"));
});

await checkAsync("run-external: captured output is capped via budget.ts", async () => {
	const r = await runExternal([NODE, "-e", "process.stdout.write('A'.repeat(10000));"], "", {
		timeoutSeconds: 15,
		outputBudgetChars: 100,
	});
	assert.equal(r.stdout.length, 100);
	assert.ok(r.stdout.endsWith(TRUNCATION_MARKER));
});

check("run-external: the default timeout is 600 seconds", () => {
	assert.equal(DEFAULT_TIMEOUT_SECONDS, 600);
});

// --- advisor-failure --------------------------------------------------------

check("advisor-failure: every hard hint classifies hard (case-insensitive)", () => {
	for (const hint of HARD_FAILURE_HINTS) {
		assert.equal(classifyAdvisorFailure(`ERROR: ${hint.toUpperCase()} while consulting`), "hard", `hint: ${hint}`);
	}
});

check("advisor-failure: soft details classify soft, including empty detail", () => {
	for (const detail of ["connection reset by peer", "malformed reply", "socket hang up", ""]) {
		assert.equal(classifyAdvisorFailure(detail), "soft", `expected soft: ${JSON.stringify(detail)}`);
	}
});

check("advisor-failure: categories name the cause, first match wins", () => {
	assert.equal(hardFailureCategory("not logged in — sign in first"), "authentication");
	assert.equal(hardFailureCategory("quota exceeded; check credits"), "quota or credits");
	assert.equal(hardFailureCategory("model 'opus' not found"), "model availability");
	assert.equal(hardFailureCategory("no error message"), null);
});

console.log(`\nshared behavior: ${passed} passed, ${failed} failed`);
if (failed > 0) {
	process.exitCode = 1;
}
