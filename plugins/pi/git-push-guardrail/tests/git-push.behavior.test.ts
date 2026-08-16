// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Behavioral tests for the git-push-guardrail deny decisions.
 *
 * Run with pi's bundled Node (native type stripping), e.g.:
 *   C:\Users\Jarry\AppData\Local\pi-node\current\node.exe
 *     plugins/pi/git-push-guardrail/tests/git-push.behavior.test.ts
 * or via the repository driver:
 *   python tests/run_pi_behavior_tests.py
 *
 * The load-bearing cases: a push hidden behind a chain (`echo hi && git
 * push`) is caught, a push with a repo-dir option (`git -C /some/dir push`)
 * is caught, while messages that merely mention push — `git commit -m
 * "push it later"`, `echo "git push"` — are not. The block must carry
 * `terminate: true`: the spike (plan Evidence 9.3) measured that it is what
 * stops the local model's retry loop.
 */

import assert from "node:assert/strict";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import gitPushGuardrail, { decide, hasGitPush } from "../extensions/git-push-guardrail.ts";

let failed = 0;
let passed = 0;

function check(label: string, ok: boolean, detail: string) {
	if (ok) {
		passed++;
		console.log(`  ok   ${label}`);
	} else {
		failed++;
		console.error(`  FAIL ${label} — ${detail}`);
	}
}

// Mandatory BLOCK cases: a push, however decorated.
const mustBlock = [
	"git push",
	"git push origin main",
	"git push --force",
	"git -C /some/dir push",
	"echo hi && git push",
];

for (const command of mustBlock) {
	check(`BLOCK  ${command}`, hasGitPush(command), "expected a git push, found none");
}

// Mandatory ALLOW cases: git that is not a push, and pushes that are only mentioned.
const mustAllow = [
	"git pull",
	"git status",
	'git commit -m "push it later"',
	'echo "git push"',
];

for (const command of mustAllow) {
	check(`ALLOW  ${command}`, !hasGitPush(command), "expected no git push, found one");
}

// Config seam: enabled:false stands the guardrail down. There is no other key —
// deliberately no per-command allowlist on a hard prohibition.
check(
	"config  enabled:false allows 'git push'",
	decide("git push", { enabled: false }).blocked === false,
	"expected the disabled guardrail to allow",
);
check(
	"config  absent config enforces with defaults",
	decide("git push", null).blocked === true,
	"expected the default config to block",
);

// --- pi glue: terminate, fail-open ---------------------------------------------

type ToolCallHandler = (event: unknown, ctx: unknown) => unknown;

function captureToolCallHandler(): ToolCallHandler {
	let captured: ToolCallHandler | null = null;
	const fakePi = {
		on(name: string, handler: unknown) {
			if (name === "tool_call") {
				captured = handler as ToolCallHandler;
			}
		},
	};
	gitPushGuardrail(fakePi as unknown as ExtensionAPI);
	if (captured === null) {
		throw new Error("the extension did not register a tool_call handler");
	}
	return captured;
}

const handler = captureToolCallHandler();

const blockResult = handler(
	{ type: "tool_call", toolName: "bash", input: { command: "git push" } },
	{ cwd: process.cwd() },
);
const blockShape = blockResult as {
	block?: unknown;
	reason?: unknown;
	terminate?: unknown;
};
check(
	"block   'git push' is blocked",
	blockResult !== undefined && blockShape.block === true,
	`expected a block result, got ${JSON.stringify(blockResult)}`,
);
check(
	"terminate  the block carries terminate:true (no retry loop)",
	blockShape.terminate === true,
	`expected terminate:true, got ${JSON.stringify(blockResult)}`,
);
check(
	"reason    the deny text names the prohibition",
	typeof blockShape.reason === "string" && blockShape.reason.includes("git-push-guardrail"),
	`expected an instructive deny reason, got ${JSON.stringify(blockResult)}`,
);
check(
	"allow     'git pull' is allowed through the handler",
	handler(
		{ type: "tool_call", toolName: "bash", input: { command: "git pull" } },
		{ cwd: process.cwd() },
	) === undefined,
	"expected undefined (allow) for a non-push git command",
);

// Pi's tool_call fails CLOSED: an unhandled throw wedges the guarded tool for
// the session. The handler body must swallow its own errors and return
// undefined, so the bash tool is allowed through.
const brokenCtx = new Proxy(
	{},
	{
		get() {
			throw new Error("induced internal error");
		},
	},
);
check(
	"fail-open  an internal error allows bash through",
	handler(
		{ type: "tool_call", toolName: "bash", input: { command: "git push" } },
		brokenCtx,
	) === undefined,
	"expected undefined (allow) when the handler throws internally",
);

console.log(`\ngit-push behavior: ${passed} passed, ${failed} failed`);
if (failed > 0) {
	process.exitCode = 1;
}
