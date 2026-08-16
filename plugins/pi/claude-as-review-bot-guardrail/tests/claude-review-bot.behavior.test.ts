// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Behavioral tests for the claude-as-review-bot-guardrail (pi host).
 *
 * Run with pi's bundled Node (native type stripping), e.g.:
 *   C:\Users\Jarry\AppData\Local\pi-node\current\node.exe
 *     plugins/pi/claude-as-review-bot-guardrail/tests/claude-review-bot.behavior.test.ts
 * or via the suite:
 *   "C:\Users\Jarry\AppData\Local\pi-node\current\node.exe" --test "plugins\pi\**\*.test.ts"
 *
 * The load-bearing case is the FIRST async case group: `agent_settled` is
 * reentrant (measured live — a probe produced three full runs, stopped only
 * by a hard counter), so the per-session cycle counter must stop the loop
 * even when the fingerprint changes every cycle. That is the test the whole
 * guardrail exists to pass.
 *
 * NO test calls the real claude CLI and no mock subprocess framework is
 * built: the guardrail's logic is pure (injectable git executor, injectable
 * review runner), and the pure parts are tested directly.
 */

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { TRUNCATION_MARKER } from "../../shared/budget.ts";
import {
	CLAUDE_REVIEW_FLAGS,
	DEFAULT_DIFF_BUDGET_BYTES,
	DEFAULT_MAX_CYCLES,
	DEFAULT_REVIEW_BUDGET_CHARS,
	DEFAULT_TIMEOUT_SECONDS,
	GUARDRAIL_NAME,
	buildReviewPrompt,
	capDiffToBytes,
	computeFingerprint,
	configDiffBudgetBytes,
	configMaxCycles,
	configReviewBudgetChars,
	configTimeoutSeconds,
	createReviewState,
	decideCycle,
	hasReviewedFingerprint,
	makeGitExecutor,
	parseStatusFiles,
	parseVerdict,
	recordFingerprint,
	rejectionMessage,
	runReview,
	runSettledReview,
	skippedReviewerMessage,
} from "../extensions/claude-as-review-bot-guardrail.ts";
import reviewBotGuardrail from "../extensions/claude-as-review-bot-guardrail.ts";

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

const asyncChecks: Array<{ label: string; fn: () => Promise<void> }> = [];
function acheck(label: string, fn: () => Promise<void>) {
	asyncChecks.push({ label, fn });
}

// --- hermetic fakes --------------------------------------------------------------

/** A hermetic project root: no config at first, then one with settings. */
const projectRoot = mkdtempSync(join(tmpdir(), "pi-review-bot-test-"));
const harnessDir = join(projectRoot, "harness", GUARDRAIL_NAME);
const harnessConfig = () => join(harnessDir, "config.json");
mkdirSync(harnessDir, { recursive: true });
function clearConfig() {
	rmSync(harnessConfig(), { force: true });
}

/** A fake `agent_settled` context with a counting notify. */
function makeCtx(overrides: Record<string, unknown> = {}) {
	const notifyCalls: Array<{ message: string; type?: string }> = [];
	const ctx = {
		mode: "tui",
		cwd: projectRoot,
		hasUI: true,
		ui: {
			notify: (message: string, type?: string) => {
				notifyCalls.push({ message, type });
			},
		},
		...overrides,
	};
	return { ctx, notifyCalls };
}

function makeSend() {
	const calls: string[] = [];
	const send = (message: string) => {
		calls.push(message);
	};
	return { send, calls };
}

/** A fake git state (the guardrail's GitExecutor result). */
function makeGit(status = " M src/app.py", diff = "diff --git a/src/app.py b/src/app.py\n+print(1)", overrides: Record<string, unknown> = {}) {
	const executor = async (cwd: string) => ({
		isRepo: true,
		hasChanges: true,
		files: parseStatusFiles(status),
		status,
		diff,
		cwd,
		...overrides,
	});
	return { executor };
}

/** A scripted reviewer: strings are replies, Errors are thrown failures. */
function makeRunner(script: Array<string | Error>) {
	const calls: Array<{ prompt: string; options: unknown }> = [];
	const runner = async (prompt: string, options: unknown) => {
		calls.push({ prompt, options });
		const item = script[Math.min(calls.length - 1, script.length - 1)];
		if (item instanceof Error) {
			throw item;
		}
		return item;
	};
	return { runner, calls };
}

// --- config seam --------------------------------------------------------------------

check("config: defaults are 2 cycles, 60000 diff bytes, 2000 reply chars, 300s", () => {
	assert.equal(DEFAULT_MAX_CYCLES, 2);
	assert.equal(DEFAULT_DIFF_BUDGET_BYTES, 60_000);
	assert.equal(DEFAULT_REVIEW_BUDGET_CHARS, 2_000);
	assert.equal(DEFAULT_TIMEOUT_SECONDS, 300);
	assert.equal(configMaxCycles(null), 2);
	assert.equal(configDiffBudgetBytes(null), 60_000);
	assert.equal(configReviewBudgetChars(null), 2_000);
	assert.equal(configTimeoutSeconds(null), 300);
});

check("config: malformed values fall back to defaults; valid ones are honored", () => {
	assert.equal(configMaxCycles({ maxCycles: "2" }), 2); // string -> default
	assert.equal(configMaxCycles({ maxCycles: -1 }), 2);
	assert.equal(configMaxCycles({ maxCycles: 3 }), 3);
	assert.equal(configDiffBudgetBytes({ diffBudgetBytes: 0 }), 60_000);
	assert.equal(configDiffBudgetBytes({ diffBudgetBytes: 10_000 }), 10_000);
	assert.equal(configReviewBudgetChars({ reviewBudgetChars: 500 }), 500);
	assert.equal(configTimeoutSeconds({ timeoutSeconds: 45 }), 45);
});

check("config: enabled:false is honored by the handler (see the glue cases below)", () => {
	// asserted behaviorally in the glue group; nothing to compute here
});

// --- the reviewer command line (verified advisor set) ---------------------------------

check("command: the flag set is exactly the verified advisor command line", () => {
	assert.deepEqual([...CLAUDE_REVIEW_FLAGS], [
		"-p",
		"--model",
		"opus",
		"--effort",
		"high",
		"--permission-mode",
		"plan",
		"--tools",
		"Read,Grep,Glob",
		"--safe-mode",
		"--no-session-persistence",
		"--output-format",
		"text",
	]);
});

// --- the fingerprint (secondary guard) -----------------------------------------------

check("fingerprint: deterministic, and different for different states", () => {
	const a = computeFingerprint(" M a.py", "diff one");
	const b = computeFingerprint(" M a.py", "diff one");
	const c = computeFingerprint(" M a.py", "diff two");
	const d = computeFingerprint(" M b.py", "diff one");
	assert.equal(a, b);
	assert.notEqual(a, c);
	assert.notEqual(a, d);
	assert.match(a, /^[0-9a-f]{64}$/u);
});

// --- diff byte capping -----------------------------------------------------------------

check("diff cap: a diff that fits passes through untouched", () => {
	const r = capDiffToBytes("diff --git a/b b/b\n+x", 60_000);
	assert.equal(r.truncated, false);
	assert.equal(r.omittedBytes, 0);
	assert.equal(r.diff, "diff --git a/b b/b\n+x");
});

check("diff cap: an over-budget diff is cut at the budget, never over", () => {
	const diff = Array.from({ length: 1000 }, (_, i) => `${i} ${"x".repeat(60)}`).join("\n");
	const total = Buffer.byteLength(diff, "utf8");
	assert.ok(total > 60_000, "precondition: the diff must exceed the budget");
	const r = capDiffToBytes(diff, 60_000);
	assert.equal(r.truncated, true);
	assert.ok(Buffer.byteLength(r.diff, "utf8") <= 60_000, "the capped diff fits the byte budget");
	assert.ok(r.omittedBytes > 0);
	assert.ok(r.diff.startsWith("0 "), "kept from the top, on a line boundary");
});

check("diff cap: a non-positive budget falls back to the default (config semantics)", () => {
	const diff = "line one\nline two";
	const r = capDiffToBytes(diff, 0);
	assert.equal(r.truncated, false, "0 is malformed, not an explicit zero: the default cap applies");
	assert.equal(r.diff, diff);
	const r2 = capDiffToBytes(diff, -5);
	assert.equal(r2.truncated, false);
});

check("parseStatusFiles: strips the two-character status column, keeps renames", () => {
	assert.deepEqual(parseStatusFiles(" M a.py\n?? new.md"), ["a.py", "new.md"]);
	assert.deepEqual(parseStatusFiles("R  old.py -> new.py"), ["old.py -> new.py"]);
	assert.deepEqual(parseStatusFiles(""), []);
	assert.deepEqual(parseStatusFiles("\n  \n"), []);
});

check("diff cap: multi-byte characters are never split mid-codepoint", () => {
	const diff = "ééé\n" + "f".repeat(100); // 7 bytes then 101 bytes
	const r = capDiffToBytes(diff, 20);
	assert.equal(r.diff, "ééé", "the first line fits; the second does not; nothing is split");
	assert.equal(r.truncated, true);
	assert.equal(Buffer.from(r.diff, "utf8").toString("utf8"), r.diff, "result is valid UTF-8");
});

// --- the review prompt -------------------------------------------------------------------

check("prompt: files, diff, the fixed reply shape, and a complete diff are stated", () => {
	const git = makeGit(" M a.py\n?? new.md", "diff --git a/a.py b/a.py\n+x");
	const prompt = buildReviewPrompt(
		{
			isRepo: true,
			hasChanges: true,
			files: ["a.py", "new.md"],
			status: " M a.py\n?? new.md",
			diff: "diff --git a/a.py b/a.py\n+x",
			cwd: projectRoot,
		},
		null,
	);
	assert.ok(prompt.includes("strict code reviewer"));
	assert.ok(prompt.includes("Do not implement or modify files"));
	assert.ok(prompt.includes("- a.py"));
	assert.ok(prompt.includes("- new.md"));
	assert.ok(prompt.includes("diff --git a/a.py b/a.py"));
	assert.ok(prompt.includes("APPROVE or REJECT"));
	assert.ok(prompt.includes("one line of problem, one line of the fix"));
	assert.ok(prompt.includes("under 2000 characters"));
	assert.ok(prompt.includes("The diff above is complete"));
	// silence the unused-variable warning for git while keeping the helper honest
	assert.ok(git.executor);
});

check("prompt: a truncated diff is said plainly, with the omitted bytes named", () => {
	const git = {
		isRepo: true,
		hasChanges: true,
		files: ["big.py"],
		status: " M big.py",
		diff: Array.from({ length: 500 }, (_, i) => `${i} ${"y".repeat(60)}`).join("\n"),
		cwd: projectRoot,
	};
	const prompt = buildReviewPrompt(git, { diffBudgetBytes: 100 });
	assert.ok(prompt.includes("TRUNCATED to 100 bytes"));
	assert.ok(prompt.includes("bytes omitted"));
	assert.ok(prompt.includes("You did not see the complete change"));
	assert.ok(!prompt.includes("The diff above is complete"));
});

// --- verdict parsing ----------------------------------------------------------------------

check("verdict: APPROVE with a body parses", () => {
	const p = parseVerdict("APPROVE\nAll good.");
	assert.equal(p?.verdict, "APPROVE");
	assert.equal(p?.body, "All good.");
});

check("verdict: REJECT with issues parses, leading blank lines are fine", () => {
	const p = parseVerdict("\n\nREJECT\nProblem: the cache is never invalidated\nFix: evict on write\n");
	assert.equal(p?.verdict, "REJECT");
	assert.ok(p?.body.includes("Problem: the cache is never invalidated"));
	assert.ok(p?.body.includes("Fix: evict on write"));
});

check("verdict: REJECT with no body parses to an empty body (malformed-ish, caller decides)", () => {
	const p = parseVerdict("REJECT");
	assert.equal(p?.verdict, "REJECT");
	assert.equal(p?.body, "");
});

check("verdict: a reply that does not open with the single word is malformed", () => {
	for (const bad of [
		"looks good to me",
		"APPROVE (with caveats)",
		"approve",
		"Verdict: REJECT. Because: the tests are red.",
		"",
		"\n   \n",
	]) {
		assert.equal(parseVerdict(bad), null, `should be malformed: ${JSON.stringify(bad)}`);
	}
});

// --- runReview: outcomes, retries, capping ---------------------------------------------------

const gitState = {
	isRepo: true,
	hasChanges: true,
	files: ["a.py"],
	status: " M a.py",
	diff: "diff --git a/a.py b/a.py\n+x",
	cwd: projectRoot,
};

acheck("runReview: APPROVE returns approved without a reply body", async () => {
	const { runner, calls } = makeRunner(["APPROVE\nSolid work."]);
	const outcome = await runReview(null, gitState, runner);
	assert.deepEqual(outcome, { outcome: "approved", attempts: 1 });
	assert.equal(calls.length, 1);
});

acheck("runReview: REJECT returns the reply HARD-CAPPED to reviewBudgetChars", async () => {
	const { runner } = makeRunner(["REJECT\n" + "p".repeat(5_000)]);
	const outcome = await runReview(null, gitState, runner);
	assert.equal(outcome.outcome, "rejected");
	if (outcome.outcome === "rejected") {
		assert.equal(outcome.review.length, 2_000);
		assert.ok(outcome.review.endsWith(TRUNCATION_MARKER));
	}
});

acheck("runReview: a project-configured reply cap is honored", async () => {
	const { runner } = makeRunner(["REJECT\n" + "q".repeat(5_000)]);
	const outcome = await runReview({ reviewBudgetChars: 500 }, gitState, runner);
	assert.equal(outcome.outcome, "rejected");
	if (outcome.outcome === "rejected") {
		assert.equal(outcome.review.length, 500);
	}
});

acheck("runReview: a MALFORMED reply is retried once within the cycle, then accepted", async () => {
	const { runner, calls } = makeRunner(["I think this is fine overall", "REJECT\nProblem: x\nFix: y"]);
	const outcome = await runReview(null, gitState, runner);
	assert.equal(outcome.outcome, "rejected");
	assert.equal(calls.length, 2, "the malformed reply cost one in-cycle retry");
});

acheck("runReview: a REJECT with no issues is malformed and retried", async () => {
	const { runner, calls } = makeRunner(["REJECT", "REJECT\nProblem: x\nFix: y"]);
	const outcome = await runReview(null, gitState, runner);
	assert.equal(outcome.outcome, "rejected");
	assert.equal(calls.length, 2);
});

acheck("runReview: the prompt the runner receives carries the truncation marking", async () => {
	const { runner, calls } = makeRunner(["APPROVE"]);
	await runReview({ diffBudgetBytes: 100 }, { ...gitState, diff: "z".repeat(1_000) }, runner);
	assert.ok(calls[0].prompt.includes("TRUNCATED to 100 bytes"));
});

// --- hard vs soft failure handling ------------------------------------------------------------

acheck("runReview: a HARD failure (auth) skips the review and does NOT retry", async () => {
	const { runner, calls } = makeRunner([new Error("Error: 403 unauthorized — authentication required")]);
	const outcome = await runReview(null, gitState, runner);
	assert.equal(outcome.outcome, "failed");
	if (outcome.outcome === "failed") {
		assert.equal(outcome.reason, "hard");
		assert.ok(outcome.error.includes("authentication"));
	}
	assert.equal(calls.length, 1, "hard failures are skipped, never retried into a loop");
});

acheck("runReview: a HARD failure (quota) skips the review and does NOT retry", async () => {
	const { runner, calls } = makeRunner([new Error("You have exceeded your usage limit; check billing.")]);
	const outcome = await runReview(null, gitState, runner);
	if (outcome.outcome !== "failed" || outcome.reason !== "hard") {
		throw new Error("expected a hard failure");
	}
	assert.equal(calls.length, 1);
});

acheck("runReview: an UNREACHABLE CLI (not found) is hard: skip, no retry loop", async () => {
	const { runner, calls } = makeRunner([new Error("claude CLI unavailable: claude was not found in the usual install locations or on PATH.")]);
	const outcome = await runReview(null, gitState, runner);
	assert.equal(outcome.outcome, "failed");
	if (outcome.outcome === "failed") {
		assert.equal(outcome.reason, "hard");
	}
	assert.equal(calls.length, 1);
});

acheck("runReview: a SOFT failure is retried within the cycle budget, then the review fails soft", async () => {
	const { runner, calls } = makeRunner([new Error("connection reset by peer")]);
	const outcome = await runReview(null, gitState, runner);
	assert.equal(outcome.outcome, "failed");
	if (outcome.outcome === "failed") {
		assert.equal(outcome.reason, "soft");
		assert.ok(outcome.error.includes("connection reset by peer"));
	}
	assert.equal(calls.length, 2, "soft failures get the in-cycle retry (maxCycles 2)");
});

acheck("runReview: a SOFT failure then a good REJECT recovers within the cycle", async () => {
	const { runner, calls } = makeRunner([new Error("socket hang up"), "REJECT\nProblem: x\nFix: y"]);
	const outcome = await runReview(null, gitState, runner);
	assert.equal(outcome.outcome, "rejected");
	assert.equal(calls.length, 2);
});

acheck("runReview: the retry budget honors maxCycles from config", async () => {
	const { runner, calls } = makeRunner([new Error("connection reset by peer")]);
	const outcome = await runReview({ maxCycles: 1 }, gitState, runner);
	if (outcome.outcome !== "failed" || outcome.reason !== "soft") {
		throw new Error("expected a soft failure");
	}
	assert.equal(calls.length, 1, "maxCycles 1 means no in-cycle retry");
});

// --- the cycle counter and fingerprint (pure) --------------------------------------------------

check("counter: a fresh session allows up to maxCycles cycles, then refuses", () => {
	const state = createReviewState();
	assert.equal(decideCycle(state, null).allowed, true);
	assert.equal(decideCycle(state, null).maxCycles, 2);
	state.cyclesUsed = 1;
	assert.equal(decideCycle(state, null).allowed, true);
	state.cyclesUsed = 2;
	assert.equal(decideCycle(state, null).allowed, false, "at maxCycles 2 the counter refuses");
});

check("counter: maxCycles from config is honored", () => {
	const state = createReviewState();
	state.cyclesUsed = 2;
	assert.equal(decideCycle(state, { maxCycles: 3 }).allowed, true);
	assert.equal(decideCycle(state, { maxCycles: 3 }).allowed, true);
	state.cyclesUsed = 3;
	assert.equal(decideCycle(state, { maxCycles: 3 }).allowed, false);
});

check("fingerprint set: records and recognizes a reviewed state", () => {
	const state = createReviewState();
	const fp = computeFingerprint(" M a.py", "diff");
	assert.equal(hasReviewedFingerprint(state, fp), false);
	recordFingerprint(state, fp);
	assert.equal(hasReviewedFingerprint(state, fp), true);
	assert.equal(hasReviewedFingerprint(state, computeFingerprint(" M a.py", "other")), false);
});

// --- messages -----------------------------------------------------------------------------------

check("rejection message: carries the capped review and the budget note", () => {
	const review = "Problem: the cache is never invalidated\nFix: evict on write";
	const mid = rejectionMessage(review, 1, 2);
	assert.ok(mid.includes(review));
	assert.ok(mid.includes("1 review cycle(s) remain"));
	const last = rejectionMessage(review, 2, 2);
	assert.ok(last.includes("last review cycle"));
});

check("skip message: a hard failure names the likely cause and the disable seam", () => {
	const msg = skippedReviewerMessage({
		outcome: "failed",
		reason: "hard",
		error: "Error: 403 unauthorized — authentication required",
		attempts: 1,
	});
	assert.ok(msg.includes("unavailable"));
	assert.ok(msg.includes("authentication"));
	assert.ok(msg.includes("skipped"));
	assert.ok(msg.includes(`harness/${GUARDRAIL_NAME}/config.json`));
});

check("skip message: a soft exhaustion reports the attempts and the cause", () => {
	const msg = skippedReviewerMessage({
		outcome: "failed",
		reason: "soft",
		error: "connection reset by peer",
		attempts: 2,
	});
	assert.ok(msg.includes("could not be completed"));
	assert.ok(msg.includes("2 attempt(s)"));
	assert.ok(msg.includes("connection reset by peer"));
	assert.ok(skippedReviewerMessage({ outcome: "failed", reason: "soft", error: "", attempts: 2 }).includes("No error message was returned."));
});

// --- glue: the agent_settled pass (fake git, fake runner, fake ctx) -------------------------------

acheck("glue: PRINT MODE STANDS DOWN IMMEDIATELY — no git, no review, no injection, no error", async () => {
	const { executor } = makeGit();
	const { runner, calls } = makeRunner(["REJECT\nProblem: x\nFix: y"]);
	const { send, calls: sends } = makeSend();
	const { ctx, notifyCalls } = makeCtx({ mode: "print" });
	const result = await runSettledReview(ctx, createReviewState(), executor, send, runner);
	assert.equal(result, "stand-down: print mode cannot host a wrap-up review");
	assert.equal(calls.length, 0, "no reviewer call in print mode");
	assert.equal(sends.length, 0, "no injection in print mode");
	assert.equal(notifyCalls.length, 0, "silent stand-down: not even a notify");
});

acheck("glue: enabled:false stands the guardrail down for that project", async () => {
	writeFileSync(harnessConfig(), JSON.stringify({ enabled: false }));
	const { runner, calls } = makeRunner(["REJECT\nProblem: x\nFix: y"]);
	const { send, calls: sends } = makeSend();
	const { ctx } = makeCtx();
	const result = await runSettledReview(ctx, createReviewState(), makeGit().executor, send, runner);
	clearConfig();
	assert.equal(result, "stand-down: disabled by project config");
	assert.equal(calls.length, 0);
	assert.equal(sends.length, 0);
});

acheck("glue: a non-git repository is skipped", async () => {
	const { runner, calls } = makeRunner(["REJECT\nProblem: x\nFix: y"]);
	const { send, calls: sends } = makeSend();
	const { ctx } = makeCtx();
	const executor = async (cwd: string) => ({
		isRepo: false,
		hasChanges: false,
		files: [],
		status: "",
		diff: "",
		cwd,
	});
	const result = await runSettledReview(ctx, createReviewState(), executor, send, runner);
	assert.equal(result, "skipped: not a git repository");
	assert.equal(calls.length, 0);
	assert.equal(sends.length, 0);
});

acheck("glue: a clean tree (no changes) is skipped", async () => {
	const { runner, calls } = makeRunner(["REJECT\nProblem: x\nFix: y"]);
	const { send, calls: sends } = makeSend();
	const { ctx } = makeCtx();
	const { executor } = makeGit("", "", { hasChanges: false, files: [] });
	const result = await runSettledReview(ctx, createReviewState(), executor, send, runner);
	assert.equal(result, "skipped: no changes to review");
	assert.equal(calls.length, 0);
	assert.equal(sends.length, 0);
});

acheck("glue: APPROVE spends ZERO agent context — notify only, no sendUserMessage", async () => {
	const { runner, calls } = makeRunner(["APPROVE\nSolid work."]);
	const { send, calls: sends } = makeSend();
	const { ctx, notifyCalls } = makeCtx();
	const state = createReviewState();
	const result = await runSettledReview(ctx, state, makeGit().executor, send, runner);
	assert.equal(result, "reviewed: approved");
	assert.equal(calls.length, 1);
	assert.equal(sends.length, 0, "APPROVE must not inject into the session");
	assert.equal(notifyCalls.length, 1);
	assert.ok(notifyCalls[0].message.includes("APPROVED"));
	assert.equal(state.cyclesUsed, 1);
});

acheck("glue: an UNCHANGED tree is skipped by the fingerprint on the second settle", async () => {
	const { runner, calls } = makeRunner(["APPROVE\nFine."]);
	const { send, calls: sends } = makeSend();
	const { ctx, notifyCalls } = makeCtx();
	const state = createReviewState();
	const { executor } = makeGit();
	const first = await runSettledReview(ctx, state, executor, send, runner);
	assert.equal(first, "reviewed: approved");
	const second = await runSettledReview(ctx, state, executor, send, runner);
	assert.equal(second, "skipped: already reviewed this session");
	assert.equal(calls.length, 1, "the unchanged tree is reviewed exactly once");
	assert.equal(sends.length, 0);
	assert.equal(notifyCalls.length, 2, "approve notify + stand-down notify");
});

acheck("glue: REJECT feeds the capped review back through sendUserMessage", async () => {
	const { runner } = makeRunner(["REJECT\n" + "Problem: the handler is not wrapped\nFix: add try/catch".repeat(100)]);
	const { send, calls } = makeSend();
	const { ctx, notifyCalls } = makeCtx();
	const result = await runSettledReview(ctx, createReviewState(), makeGit().executor, send, runner);
	assert.equal(result, "reviewed: rejected");
	assert.equal(calls.length, 1);
	assert.ok(calls[0].includes("REJECTed this session's change set"));
	assert.ok(calls[0].includes("Problem: the handler is not wrapped"));
	assert.ok(calls[0].length < 4_000, "the injected message stays small (capped review + framing)");
	assert.equal(notifyCalls.length, 1);
});

acheck("glue: THE CRITICAL CASE — the counter stops the loop even when the fingerprint changes every cycle", async () => {
	// This is the case the fingerprint cannot catch (measured live, §9.6):
	// the agent edits files each cycle, the tree differs every time, and only
	// the hard per-session counter stops the review loop.
	const rejecter = ["REJECT\nProblem: still wrong\nFix: fix it more"];
	const { runner, calls } = makeRunner(rejecter);
	const { send, calls: sends } = makeSend();
	const { ctx, notifyCalls } = makeCtx();
	const state = createReviewState(); // maxCycles default 2

	const cycleA = await runSettledReview(ctx, state, makeGit(" M a.py", "diff A").executor, send, runner);
	assert.equal(cycleA, "reviewed: rejected");

	const cycleB = await runSettledReview(ctx, state, makeGit(" M a.py", "diff B").executor, send, runner);
	assert.equal(cycleB, "reviewed: rejected");

	const cycleC = await runSettledReview(ctx, state, makeGit(" M a.py", "diff C").executor, send, runner);
	assert.equal(cycleC, "skipped: per-session cycle budget spent");

	assert.equal(calls.length, 2, "exactly maxCycles reviews — no third");
	assert.equal(sends.length, 2, "exactly two injections — the counter, not the fingerprint, stopped the loop");
	assert.ok(
		notifyCalls.some((call) => call.message.includes("per-session review budget (2 cycle(s)) is spent")),
		"the operator is told the budget is spent",
	);
});

acheck("glue: a HARD review failure skips the review, notifies, never injects, and does not re-fire on the same tree", async () => {
	const { runner, calls } = makeRunner([new Error("Error: not logged in. Run 'claude login' to sign in.")]);
	const { send, calls: sends } = makeSend();
	const { ctx, notifyCalls } = makeCtx();
	const state = createReviewState();
	const { executor } = makeGit();

	const first = await runSettledReview(ctx, state, executor, send, runner);
	assert.equal(first, "skipped: reviewer unavailable (hard failure)");
	assert.equal(sends.length, 0, "a hard failure never injects");
	assert.equal(calls.length, 1, "no retry on a hard failure");
	assert.ok(notifyCalls[0].message.includes("authentication"));

	const second = await runSettledReview(ctx, state, executor, send, runner);
	assert.equal(second, "skipped: already reviewed this session", "the same tree is not re-reviewed while the reviewer is down");
	assert.equal(calls.length, 1);
});

acheck("glue: a SOFT review failure is reported, never injected, never wedged", async () => {
	const { runner, calls } = makeRunner([new Error("connection reset by peer")]);
	const { send, calls: sends } = makeSend();
	const { ctx, notifyCalls } = makeCtx();
	const result = await runSettledReview(ctx, createReviewState(), makeGit().executor, send, runner);
	assert.equal(result, "failed: reviewer retries exhausted (soft)");
	assert.equal(sends.length, 0, "a failed review never injects");
	assert.equal(calls.length, 2, "the in-cycle soft retry happened");
	assert.ok(notifyCalls[0].message.includes("could not be completed"));
});

acheck("glue: a REJECT whose feedback CANNOT be delivered still stands down safely", async () => {
	const explodingSend = () => {
		throw new Error("This extension ctx is stale after session replacement or reload.");
	};
	const { runner } = makeRunner(["REJECT\nProblem: x\nFix: y"]);
	const { ctx, notifyCalls } = makeCtx();
	const result = await runSettledReview(ctx, createReviewState(), makeGit().executor, explodingSend, runner);
	assert.equal(result, "reviewed: rejected (feedback undelivered)");
	assert.equal(notifyCalls.length, 1, "the operator still sees what happened");
	assert.ok(notifyCalls[0].message.includes("could not be delivered"));
});

// --- makeGitExecutor: the pi.exec-backed executor ----------------------------------------------

acheck("git executor: resolves repo, changes, files, and diff from pi.exec", async () => {
	const map: Record<string, { stdout: string; code: number }> = {
		"rev-parse --is-inside-work-tree": { stdout: "true\n", code: 0 },
		"status --porcelain": { stdout: " M a.py\n?? new.md\n", code: 0 },
		"diff HEAD": { stdout: "diff --git a/a.py b/a.py\n+x\n", code: 0 },
	};
	const execCalls: string[][] = [];
	const executor = makeGitExecutor({
		exec: async (_command, args) => {
			execCalls.push(args);
			const key = args.join(" ");
			const r = map[key] ?? { stdout: "", code: 1 };
			return { stdout: r.stdout, stderr: "", code: r.code };
		},
	});
	const state = await executor(projectRoot);
	assert.equal(state.isRepo, true);
	assert.equal(state.hasChanges, true);
	assert.deepEqual(state.files, ["a.py", "new.md"]);
	assert.ok(state.diff.includes("diff --git"));
	assert.deepEqual(execCalls, [
		["rev-parse", "--is-inside-work-tree"],
		["status", "--porcelain"],
		["diff", "HEAD"],
	]);
});

acheck("git executor: a non-repository resolves to isRepo:false, never throws", async () => {
	const executor = makeGitExecutor({
		exec: async (_command, args) => {
			if (args[0] === "rev-parse") {
				return { stdout: "", stderr: "fatal: not a git repository", code: 128 };
			}
			return { stdout: "", stderr: "", code: 1 };
		},
	});
	const state = await executor(projectRoot);
	assert.equal(state.isRepo, false);
	assert.equal(state.hasChanges, false);
});

acheck("git executor: a clean tree is hasChanges:false", async () => {
	const executor = makeGitExecutor({
		exec: async (_command, args) => {
			if (args[0] === "rev-parse") {
				return { stdout: "true\n", stderr: "", code: 0 };
			}
			return { stdout: "", stderr: "", code: 0 };
		},
	});
	const state = await executor(projectRoot);
	assert.equal(state.isRepo, true);
	assert.equal(state.hasChanges, false);
	assert.deepEqual(state.files, []);
});

// --- the extension entry point ---------------------------------------------------------------

check("entry: the extension subscribes to agent_settled (not agent_end)", () => {
	const seen: string[] = [];
	const fakePi = {
		on: (name: string, _handler: unknown) => {
			seen.push(name);
		},
		exec: async () => {
			throw new Error("not used in this test");
		},
		sendUserMessage: () => {},
	};
	reviewBotGuardrail(fakePi as unknown as ExtensionAPI);
	assert.deepEqual(seen, ["agent_settled"], "exactly one subscription, on the settled event");
});

acheck("entry: an internal error in the settled handler NEVER throws out (fail-safe)", async () => {
	let handler: ((event: unknown, ctx: unknown) => unknown) | null = null;
	const fakePi = {
		on: (_name: string, h: unknown) => {
			handler = h as (event: unknown, ctx: unknown) => unknown;
		},
		// git explodes: the handler must swallow it, not surface it.
		exec: async () => {
			throw new Error("git exploded (induced)");
		},
		sendUserMessage: () => {},
	};
	reviewBotGuardrail(fakePi as unknown as ExtensionAPI);
	assert.equal(typeof handler, "function");
	assert.doesNotThrow(() => {
		handler?.({ type: "agent_settled" }, { mode: "tui", cwd: projectRoot });
	});
	// Give the internal promise a beat: any unhandled rejection would fail
	// the whole process, which is exactly what the .catch must prevent.
	await new Promise((resolve) => {
		setTimeout(resolve, 25);
	});
});

// --- run the async checks, then report -----------------------------------------------------------

for (const { label, fn } of asyncChecks) {
	try {
		await fn();
		passed++;
		console.log(`  ok   ${label}`);
	} catch (err) {
		failed++;
		console.error(`  FAIL ${label} — ${err instanceof Error ? err.message : String(err)}`);
	}
}

console.log(`\nclaude-as-review-bot behavior: ${passed} passed, ${failed} failed`);
if (failed > 0) {
	process.exitCode = 1;
}
