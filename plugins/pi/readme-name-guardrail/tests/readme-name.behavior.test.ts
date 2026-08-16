// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Behavioral tests for the readme-name-guardrail deny decisions.
 *
 * Run with pi's bundled Node (native type stripping), e.g.:
 *   C:\Users\Jarry\AppData\Local\pi-node\current\node.exe
 *     plugins/pi/readme-name-guardrail/tests/readme-name.behavior.test.ts
 * or via the repository driver:
 *   python tests/run_pi_behavior_tests.py
 *
 * The load-bearing rule: a path is forbidden when its filename is exactly
 * `readme.md` (any casing) and its parent is not the project root. The
 * guardrail's own suggested remedy — a prefixed name — must never be blocked.
 */

import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import readmeGuardrail, {
	decideGit,
	decideWrite,
	suggestedReadmeName,
} from "../extensions/readme-name-guardrail.ts";

const root = mkdtempSync(join(tmpdir(), "pi-readme-guardrail-test-"));

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

// --- write / edit path: mandatory BLOCK cases --------------------------------

const mustBlockWrite = [
	"docs/readme.md",
	"docs/README.md",
	"src/sub/Readme.md",
];

for (const filePath of mustBlockWrite) {
	const decision = decideWrite(filePath, root);
	check(
		`BLOCK  write ${filePath}`,
		decision.blocked === true && decision.offenders.length === 1,
		`expected a blocked readme, got ${JSON.stringify(decision)}`,
	);
}

// --- write / edit path: mandatory ALLOW cases --------------------------------

const mustAllowWrite = [
	"README.md", // the single allowed project-root README
	"docs/api-readme.md",
	"docs/readme-template.md",
];

for (const filePath of mustAllowWrite) {
	const decision = decideWrite(filePath, root);
	check(
		`ALLOW  write ${filePath}`,
		decision.blocked === false,
		`expected the path to be allowed, got ${JSON.stringify(decision)}`,
	);
}

// --- git path: mandatory BLOCK and ALLOW cases --------------------------------

const mustBlockGit = [
	"git add docs/readme.md",
	"git commit docs/readme.md",
];

for (const command of mustBlockGit) {
	const decision = decideGit(command, root);
	check(
		`BLOCK  bash ${command}`,
		decision.blocked === true && decision.offenders.length >= 1,
		`expected a blocked git command, got ${JSON.stringify(decision)}`,
	);
}

const mustAllowGit = [
	"git add src/main.ts",
	"git pull",
];

for (const command of mustAllowGit) {
	const decision = decideGit(command, root);
	check(
		`ALLOW  bash ${command}`,
		decision.blocked === false,
		`expected the git command to be allowed, got ${JSON.stringify(decision)}`,
	);
}

// --- the suggestion: per-path, and its remedy is not blocked ------------------

const suggestion = suggestedReadmeName(join(root, "docs", "readme.md"));
check(
	"suggest  docs/readme.md -> docs-readme.md",
	suggestion === "docs-readme.md",
	`expected 'docs-readme.md', got '${suggestion}'`,
);
check(
	"remedy not blocked: the suggested name is allowed",
	decideWrite(join("docs", "docs-readme.md"), root).blocked === false,
	"the deny message recommends a name the guardrail itself blocks",
);

// --- config seam ----------------------------------------------------------------

check(
	"config  enabled:false allows 'docs/readme.md'",
	decideWrite("docs/readme.md", root, { enabled: false }).blocked === false,
	"expected the disabled guardrail to allow",
);
check(
	"config  enabled:false allows 'git add docs/readme.md'",
	decideGit("git add docs/readme.md", root, { enabled: false }).blocked === false,
	"expected the disabled guardrail to allow",
);
check(
	"config  allowPaths regex exempts a declared nested path",
	decideWrite("docs/generated/readme.md", root, { allowPaths: ["^docs/generated/"] }).blocked ===
		false,
	"expected the allowlisted path to be allowed",
);
check(
	"config  allowPaths does not exempt a nested path outside its prefix",
	decideWrite("src/generated/readme.md", root, { allowPaths: ["^docs/generated/"] }).blocked ===
		true,
	"expected the unlisted path to stay blocked",
);
check(
	"config  allowPaths is inert for the already-allowed root README",
	decideWrite("readme.md", root, { allowPaths: ["^"] }).blocked === false,
	"expected the root README to be allowed",
);

// --- pi glue: internal error must FAIL OPEN ------------------------------------
// Pi's tool_call fails CLOSED: an unhandled throw wedges the guarded tool for
// the session. The handler body must swallow its own errors and return
// undefined, so the guarded tool is allowed through.

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
	readmeGuardrail(fakePi as unknown as ExtensionAPI);
	if (captured === null) {
		throw new Error("the extension did not register a tool_call handler");
	}
	return captured;
}

const handler = captureToolCallHandler();

// A ctx whose property access throws simulates an internal guardrail error.
const brokenCtx = new Proxy(
	{},
	{
		get() {
			throw new Error("induced internal error");
		},
	},
);

check(
	"fail-open  an internal error allows write through",
	handler({ type: "tool_call", toolName: "write", input: { path: "docs/readme.md" } }, brokenCtx) ===
		undefined,
	"expected undefined (allow) when the handler throws internally",
);
check(
	"fail-open  an internal error allows bash through",
	handler(
		{ type: "tool_call", toolName: "bash", input: { command: "git add docs/readme.md" } },
		brokenCtx,
	) === undefined,
	"expected undefined (allow) when the handler throws internally",
);

console.log(`\nreadme-name behavior: ${passed} passed, ${failed} failed`);
if (failed > 0) {
	process.exitCode = 1;
}
