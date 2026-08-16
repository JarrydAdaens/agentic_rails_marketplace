// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Behavioral tests for the cursor-as-advisor-guardrail (pi host).
 *
 * Run with pi's bundled Node (native type stripping), e.g.:
 *   C:\Users\Jarry\AppData\Local\pi-node\current\node.exe
 *     plugins/pi/cursor-as-advisor-guardrail/tests/cursor-advisor.behavior.test.ts
 * or via the repository driver:
 *   python tests/run_pi_behavior_tests.py
 *
 * The load-bearing cases: the command line is the verified one (agent
 * --print --output-format text --mode ask --sandbox disabled --trust
 * --model cursor-grok-4.6-high, prompt on UTF-8 stdin), it NEVER carries
 * --force/--yolo/--auto-review, a HARD failure (authentication, quota,
 * model availability) disarms the gate while a SOFT failure keeps it armed,
 * the reply is capped before it reaches the model, and the gate state
 * machine denies before a successful consult and allows after one. NO test
 * calls the real cursor CLI and no mock subprocess framework is built: the
 * pure parts are tested directly.
 */

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { classifyAdvisorFailure, hardFailureCategory, HARD_FAILURE_HINTS } from "../../shared/advisor-failure.ts";
import { capToBudget, TRUNCATION_MARKER } from "../../shared/budget.ts";
import {
	DEFAULT_MODEL,
	DEFAULT_REPLY_BUDGET_CHARS,
	DEFAULT_TIMEOUT_SECONDS,
	GUARDRAIL_NAME,
	applyConsultOutcome,
	buildPrompt,
	configModel,
	configReplyBudgetChars,
	configTimeoutSeconds,
	createGate,
	cursorAdvisorFlags,
	denyReason,
	failedAdvisorMessage,
	gateAllowsWrite,
	hardFailureMessage,
	timeoutAdvisorMessage,
	unreachableAdvisorMessage,
	validateConsult,
} from "../extensions/cursor-as-advisor-guardrail.ts";
import cursorAdvisorGuardrail from "../extensions/cursor-as-advisor-guardrail.ts";

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

// A hermetic project root: no config at first, then one with settings.
const projectRoot = mkdtempSync(join(tmpdir(), "pi-cursor-advisor-test-"));
const harnessDir = join(projectRoot, "harness", GUARDRAIL_NAME);
const harnessConfig = () => join(harnessDir, "config.json");
mkdirSync(harnessDir, { recursive: true });

// --- consult arguments -----------------------------------------------------------

check("validate: a complete consult is accepted and trimmed", () => {
	const r = validateConsult({
		task: "  ship the pi port  ",
		stage: "planning",
		approach: "shared modules first",
		evidence: "tests green",
		question: "is this the right seam?",
	});
	assert.equal(r.error, null);
	assert.equal(r.values?.task, "ship the pi port");
	assert.equal(r.values?.stage, "planning");
});

check("validate: all four stages are accepted", () => {
	for (const stage of ["planning", "stuck", "pivot-check", "completion-review"]) {
		const r = validateConsult({
			task: "t",
			stage,
			approach: "a",
			evidence: "e",
			question: "q",
		});
		assert.equal(r.error, null, `stage ${stage} should be valid`);
	}
});

check("validate: missing and empty fields are named", () => {
	const r = validateConsult({ stage: "planning", approach: "  ", evidence: "e", question: "q" });
	assert.equal(r.values, null);
	assert.ok((r.error ?? "").includes("task"));
	assert.ok((r.error ?? "").includes("approach"));
});

check("validate: a bad stage is rejected with the valid list", () => {
	const r = validateConsult({
		task: "t",
		stage: "gossip",
		approach: "a",
		evidence: "e",
		question: "q",
	});
	assert.equal(r.values, null);
	assert.ok((r.error ?? "").includes("planning, stuck, pivot-check, completion-review"));
});

check("validate: a non-object is rejected and names consult_cursor_advisor", () => {
	for (const bad of [null, "consult", ["t", "a", "e", "q"], 42]) {
		const r = validateConsult(bad);
		assert.equal(r.values, null, `${JSON.stringify(bad)} should be rejected`);
		assert.ok((r.error ?? "").includes("consult_cursor_advisor"));
	}
});

// --- prompt shape (same constructive shape as the other advisors) ------------------

check("prompt: persona, forward-path rule, and structured fields are present", () => {
	const v = validateConsult({
		task: "ship the pi port",
		stage: "stuck",
		approach: "shared modules first",
		evidence: "tests green",
		question: "is this the right seam?",
	}).values;
	const prompt = buildPrompt(v as NonNullable<typeof v>);
	assert.ok(prompt.includes("constructive senior engineering advisor"));
	assert.ok(prompt.includes("Pair every concern with a forward path"));
	assert.ok(prompt.includes("Do not implement or modify files"));
	assert.ok(prompt.includes("TASK: ship the pi port"));
	assert.ok(prompt.includes("STAGE: stuck"));
	assert.ok(prompt.includes("QUESTION: is this the right seam?"));
	assert.ok(prompt.includes("Structured consultation:"));
});

// --- the command line (verified) --------------------------------------------------

check("command: the default flag set is exactly the verified one", () => {
	assert.deepEqual(cursorAdvisorFlags(DEFAULT_MODEL), [
		"--print",
		"--output-format",
		"text",
		"--mode",
		"ask",
		"--sandbox",
		"disabled",
		"--trust",
		"--model",
		"cursor-grok-4.6-high",
	]);
});

check("command: ask mode is read-only and the OS sandbox is explicitly disabled", () => {
	const flags = [...cursorAdvisorFlags(DEFAULT_MODEL)];
	assert.ok(flags.includes("--mode") && flags[flags.indexOf("--mode") + 1] === "ask");
	assert.ok(flags.includes("--sandbox") && flags[flags.indexOf("--sandbox") + 1] === "disabled");
});

check("command: NEVER carries --force, --yolo, --auto-review, or MCP auto-approval", () => {
	const flags = [...cursorAdvisorFlags(DEFAULT_MODEL)];
	for (const forbidden of ["--force", "--yolo", "--auto-review", "--dangerously-bypass-approvals"]) {
		assert.ok(!flags.includes(forbidden), `${forbidden} must never appear on the advisor command`);
	}
});

check("command: the model is configurable but the default is the verified one", () => {
	assert.equal(DEFAULT_MODEL, "cursor-grok-4.6-high");
	assert.equal(configModel(null), "cursor-grok-4.6-high");
	assert.equal(cursorAdvisorFlags("cursor-grok-4.6-medium").at(-1), "cursor-grok-4.6-medium");
});

check("command: a .cmd shim is spawned through cmd.exe /d /c, flags after it", () => {
	const shim = "C:\\Users\\jarry\\AppData\\Local\\cursor-agent\\agent.cmd";
	const cmd = "C:\\Windows\\System32\\cmd.exe";
	const argv = [cmd, "/d", "/c", shim, ...cursorAdvisorFlags(DEFAULT_MODEL)];
	assert.deepEqual(argv.slice(0, 4), [cmd, "/d", "/c", shim]);
	assert.equal(argv[4], "--print");
	assert.equal(argv[argv.length - 1], DEFAULT_MODEL);
});

check("command: the prompt never travels on the command line (stdin only)", () => {
	// No flag value slot is left for a prompt: every odd-indexed value
	// belongs to the flag set above; the runner writes the prompt to stdin.
	const flags = [...cursorAdvisorFlags(DEFAULT_MODEL)];
	assert.equal(flags.length % 2, 0, "flag list is fully paired — nothing for a prompt");
});

// --- reply capping -----------------------------------------------------------------

check("reply: the default budget is 4000 characters", () => {
	assert.equal(DEFAULT_REPLY_BUDGET_CHARS, 4000);
	assert.equal(configReplyBudgetChars(null), 4000);
	assert.equal(configReplyBudgetChars({ reply_budget_chars: "100" }), 4000); // malformed -> default
});

check("reply: an over-budget advisor reply is capped with the marker", () => {
	const reply = "x".repeat(5000);
	const capped = capToBudget(reply, configReplyBudgetChars(null));
	assert.equal(capped.length, 4000);
	assert.ok(capped.endsWith(TRUNCATION_MARKER));
});

check("reply: a project-configured budget is honored", () => {
	const reply = "y".repeat(1000);
	const capped = capToBudget(reply, configReplyBudgetChars({ reply_budget_chars: 100 }));
	assert.equal(capped.length, 100);
	assert.ok(capped.endsWith(TRUNCATION_MARKER));
});

check("reply: a short reply passes through unchanged", () => {
	assert.equal(capToBudget("looks good", 4000), "looks good");
});

// --- failure classification and the resulting gate state ----------------------------

check("classify: every HARD_FAILURE_HINT marks a hard failure", () => {
	for (const hint of HARD_FAILURE_HINTS) {
		assert.equal(classifyAdvisorFailure(`The advisor failed: ${hint} today`), "hard", `hint: ${hint}`);
	}
});

check("classify: transient, malformed, and empty detail are soft", () => {
	for (const detail of ["connection reset by peer", "malformed JSON in the advisor reply", "socket hang up", ""]) {
		assert.equal(classifyAdvisorFailure(detail), "soft", `expected soft: ${JSON.stringify(detail)}`);
	}
});

check("classify: sign-in and model-availability failures are hard", () => {
	assert.equal(classifyAdvisorFailure("You are not logged in. Sign in to Cursor to continue."), "hard");
	assert.equal(hardFailureCategory("not logged in"), "authentication");
	assert.equal(hardFailureCategory("model cursor-grok-4.6-high not found"), "model availability");
	assert.equal(classifyAdvisorFailure("socket hang up"), "soft");
});

// --- the gate state machine --------------------------------------------------------

check("gate: armed denies writes before any consult", () => {
	const gate = createGate();
	assert.equal(gate.state, "armed");
	assert.equal(gateAllowsWrite(gate), false);
});

check("gate: a successful consult satisfies the gate", () => {
	const gate = createGate();
	applyConsultOutcome(gate, { kind: "succeeded" });
	assert.equal(gate.state, "satisfied");
	assert.equal(gateAllowsWrite(gate), true);
});

check("gate: an unreachable CLI disarms the gate (never wedges the session)", () => {
	const gate = createGate();
	applyConsultOutcome(gate, { kind: "unreachable" });
	assert.equal(gate.state, "disarmed");
	assert.equal(gateAllowsWrite(gate), true);
});

check("gate: a timed-out consult disarms the gate", () => {
	const gate = createGate();
	applyConsultOutcome(gate, { kind: "timedout" });
	assert.equal(gate.state, "disarmed");
	assert.equal(gateAllowsWrite(gate), true);
});

check("gate: a HARD failure (unusable advisor) disarms the gate — no wedge", () => {
	for (const detail of [
		"You are not logged in. Sign in to Cursor to continue.",
		"403 unauthorized: authentication required",
		"usage limit reached for this Cursor account",
		"model 'cursor-grok-4.6-high' not available",
	]) {
		assert.equal(classifyAdvisorFailure(detail), "hard", `expected hard: ${detail}`);
		const gate = createGate();
		applyConsultOutcome(gate, { kind: "hard_failed" });
		assert.equal(gate.state, "disarmed", `expected disarmed for: ${detail}`);
		assert.equal(gateAllowsWrite(gate), true, `expected writes allowed for: ${detail}`);
	}
});

check("gate: a SOFT failure (transient, one-off) keeps the gate armed", () => {
	const gate = createGate();
	applyConsultOutcome(gate, { kind: "failed" });
	assert.equal(gate.state, "armed");
	assert.equal(gateAllowsWrite(gate), false);
});

check("gate: once disarmed, the gate stays open", () => {
	const gate = createGate();
	applyConsultOutcome(gate, { kind: "hard_failed" });
	applyConsultOutcome(gate, { kind: "failed" }); // no re-arm on failure
	assert.equal(gate.state, "disarmed");
	assert.equal(gateAllowsWrite(gate), true);
});

// --- messages ------------------------------------------------------------------------

check("deny reason: names the offending write and the remedy", () => {
	const r = denyReason("src/app.py");
	assert.ok(r.includes("src/app.py"));
	assert.ok(r.includes("consult_cursor_advisor"));
	assert.ok(r.includes("expected behavior, not an error"));
});

check("deny reason: works when no path is known", () => {
	assert.ok(denyReason(null).includes("this write"));
});

check("messages: unreachable, timeout, and hard failure disarm; soft stays armed", () => {
	assert.ok(unreachableAdvisorMessage("agent not found").includes("disarmed"));
	assert.ok(timeoutAdvisorMessage("The external CLI timed out after 600s.").includes("disarmed"));
	assert.ok(failedAdvisorMessage("connection reset by peer", undefined).includes("stays armed"));
	assert.ok(failedAdvisorMessage("", "no note").includes("no note"));
	assert.ok(failedAdvisorMessage("", undefined).includes("No error message was returned."));
});

check("messages: a hard failure reports the cause AND disarms the gate", () => {
	const msg = hardFailureMessage("You are not logged in. Sign in to Cursor to continue.");
	assert.ok(msg.includes("disarmed"));
	assert.ok(msg.includes("authentication"));
	assert.ok(hardFailureMessage("quota exhausted").includes("quota or credits"));
	assert.ok(hardFailureMessage("").includes("No error message was returned."));
});

// --- config seam ----------------------------------------------------------------------

check("config: defaults are 600s timeout, 4000-char reply, cursor-grok-4.6-high", () => {
	assert.equal(DEFAULT_TIMEOUT_SECONDS, 600);
	assert.equal(configTimeoutSeconds(null), 600);
	assert.equal(configTimeoutSeconds({ consult_timeout_seconds: -5 }), 600); // malformed -> default
	assert.equal(configModel(null), "cursor-grok-4.6-high");
});

check("config: model honors a non-empty string, falls back otherwise", () => {
	assert.equal(configModel({ model: "cursor-grok-4.6-medium" }), "cursor-grok-4.6-medium");
	assert.equal(configModel({ model: "  " }), "cursor-grok-4.6-high"); // empty -> default
	assert.equal(configModel({ model: null }), "cursor-grok-4.6-high"); // malformed -> default
});

check("config: the effort key is accepted for parity but never reaches the command", () => {
	// The Cursor CLI takes no effort flag: the model id encodes the tier.
	const flags = [...cursorAdvisorFlags(configModel({ effort: "high" }))];
	assert.ok(!flags.some((flag) => flag.toLowerCase().includes("effort")));
});

check("config: a project-configured timeout is honored", () => {
	assert.equal(configTimeoutSeconds({ consult_timeout_seconds: 90 }), 90);
});

// --- pi glue: the tool and the write gate ---------------------------------------------

type ToolCallHandler = (event: unknown, ctx: unknown) => unknown;

function loadExtension() {
	let handler: ToolCallHandler | null = null;
	let tool: { name?: unknown; promptSnippet?: unknown; promptGuidelines?: unknown } | null = null;
	const fakePi = {
		on(name: string, h: unknown) {
			if (name === "tool_call") {
				handler = h as ToolCallHandler;
			}
		},
		registerTool(def: unknown) {
			tool = def as (typeof tool & object) | null;
		},
	};
	cursorAdvisorGuardrail(fakePi as unknown as ExtensionAPI);
	if (handler === null || tool === null) {
		throw new Error("the extension registered neither a tool nor a tool_call handler");
	}
	return { handler, tool: tool as { name?: unknown; promptSnippet?: unknown; promptGuidelines?: unknown } };
}

const { handler, tool } = loadExtension();

check("tool: exactly the MCP-replacement tool, named consult_cursor_advisor", () => {
	assert.equal(tool.name, "consult_cursor_advisor");
});

check("tool: promptSnippet is ONE short line for the 131k system prompt", () => {
	assert.equal(typeof tool.promptSnippet, "string");
	assert.ok(!String(tool.promptSnippet).includes("\n"));
	assert.ok((String(tool.promptSnippet) ?? "").length < 160);
});

check("tool: at most two promptGuidelines", () => {
	assert.ok(Array.isArray(tool.promptGuidelines));
	assert.ok((tool.promptGuidelines?.length ?? 0) <= 2);
});

const writeEvent = {
	type: "tool_call",
	toolName: "write",
	// Pi's write input field is `path` — NOT the `file_path` of the Claude
	// Code and Cursor hook payloads.
	input: { path: "src/app.py", content: "print(1)" },
};

check("gate (glue): the first write is denied while armed", () => {
	const r = handler(writeEvent, { cwd: projectRoot }) as { block?: unknown; reason?: unknown };
	assert.equal(r?.block, true);
	assert.ok(String(r?.reason).includes("consult_cursor_advisor"));
	assert.ok(String(r?.reason).includes("src/app.py"));
});

check("gate (glue): edit is denied while armed too", () => {
	const r = handler(
		{ type: "tool_call", toolName: "edit", input: { path: "src/app.py", edits: [] } },
		{ cwd: projectRoot },
	) as { block?: unknown };
	assert.equal(r?.block, true);
});

check("gate (glue): a write without any path is still denied while armed", () => {
	const r = handler({ type: "tool_call", toolName: "write", input: {} }, { cwd: projectRoot }) as {
		block?: unknown;
		reason?: unknown;
	};
	assert.equal(r?.block, true);
	assert.ok(String(r?.reason).includes("this write"));
});

check("gate (glue): other tools pass untouched while armed", () => {
	assert.equal(
		handler({ type: "tool_call", toolName: "bash", input: { command: "git status" } }, { cwd: projectRoot }),
		undefined,
	);
	assert.equal(handler({ type: "tool_call", toolName: "read", input: { path: "a.md" } }, { cwd: projectRoot }), undefined);
});

check("gate (glue): enabled:false stands the guardrail down for that project", () => {
	writeFileSync(harnessConfig(), JSON.stringify({ enabled: false }));
	assert.equal(handler(writeEvent, { cwd: projectRoot }), undefined);
});

check("config seam: absent config means enforce with defaults (gate still armed)", () => {
	// Remove the config file again: absent -> enforce.
	rmSync(harnessConfig(), { force: true });
	const r = handler(writeEvent, { cwd: projectRoot }) as { block?: unknown };
	assert.equal(r?.block, true);
});

// Pi's tool_call fails CLOSED: an unhandled throw wedges write and edit for
// the session. The handler body must swallow its own errors and return
// undefined, so the guarded tools are allowed through.
const brokenCtx = new Proxy(
	{},
	{
		get() {
			throw new Error("induced internal error");
		},
	},
);

check("fail-open: an internal error allows write through while armed", () => {
	assert.equal(handler(writeEvent, brokenCtx), undefined);
});

check("fail-open: an internal error allows edit through while armed", () => {
	assert.equal(
		handler({ type: "tool_call", toolName: "edit", input: { path: "x", edits: [] } }, brokenCtx),
		undefined,
	);
});

console.log(`\ncursor-as-advisor behavior: ${passed} passed, ${failed} failed`);
if (failed > 0) {
	process.exitCode = 1;
}
