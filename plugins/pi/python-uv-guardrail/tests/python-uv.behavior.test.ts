// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Behavioral tests for the python-uv-guardrail deny decisions.
 *
 * Run with pi's bundled Node (native type stripping), e.g.:
 *   C:\Users\Jarry\AppData\Local\pi-node\current\node.exe
 *     plugins/pi/python-uv-guardrail/tests/python-uv.behavior.test.ts
 * or via the repository driver:
 *   python tests/run_pi_behavior_tests.py
 *
 * The "uv run python --version" case is the load-bearing one: the spike
 * (plan Evidence 9.2) shipped a guardrail that blocked the exact remedy its
 * own error message recommended, and the local model burned six tool calls
 * fighting it.
 */

import assert from "node:assert/strict";

import { decide, findBareInterpreter } from "../extensions/python-uv-guardrail.ts";

// Mandatory BLOCK cases: a bare interpreter/installer, however decorated.
const mustBlock = [
	"python --version",
	"sudo python x.py",
	"FOO=1 python x.py",
	"cat x | python",
	"/usr/bin/python3.12 x.py",
	"C:\\Python314\\python.exe x.py",
	"pip install x",
];

// Mandatory ALLOW cases: the guardrail's own recommended remedies and their kin.
const mustAllow = [
	"uv run python --version", // the Evidence 9.2 regression
	"uvx ruff",
	"uv pip install x",
	"uv --version",
];

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

for (const command of mustBlock) {
	const offender = findBareInterpreter(command);
	check(
		`BLOCK  ${command}`,
		offender !== null,
		`expected a blocked interpreter, found none`,
	);
}

for (const command of mustAllow) {
	const offender = findBareInterpreter(command);
	check(
		`ALLOW  ${command}`,
		offender === null,
		`expected no blocked interpreter, found '${offender}'`,
	);
}

// Config seam: enabled:false stands the guardrail down...
check(
	"config  enabled:false allows 'python --version'",
	decide("python --version", { enabled: false }).blocked === false,
	"expected the disabled guardrail to allow",
);

// ...and an explicit allowCommands entry wins over the blocked pattern.
check(
	"config  allowCommands wins for a matching command",
	decide("python --version", { allowCommands: ["--version$"] }).blocked === false,
	"expected the allowlisted command to be allowed",
);

// A deny message must never recommend a remedy the same guardrail blocks.
const offender = findBareInterpreter("python --version");
if (offender !== null) {
	const remedies = [
		`uv run python --version`,
		"uv run x.py",
		"uv pip install requests",
		"uvx ruff",
	];
	for (const remedy of remedies) {
		check(
			`remedy not blocked: ${remedy}`,
			findBareInterpreter(remedy) === null,
			`the deny message recommends a command the guardrail itself blocks`,
		);
	}
}

console.log(
	`\npython-uv behavior: ${passed} passed, ${failed} failed`
);
if (failed > 0) {
	process.exitCode = 1;
}
