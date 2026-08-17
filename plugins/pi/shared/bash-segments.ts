// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Shell-command segmentation for pi guardrails.
 *
 * Pure, side-effect-free functions shared by every guardrail that inspects
 * bash commands. The goal is to find the *leading executable* of each
 * simple-command segment, so a bare `python` hidden behind a pipe, a chain,
 * a subshell, an inline assignment, or a wrapper is still caught, while a
 * legitimate delegation such as `uv run python ...` is not.
 *
 * This is an independent reimplementation of the decision logic in
 * plugins/cursor/python-uv-guardrail/hooks/enforce-uv-python.ps1; the two
 * files intentionally share no code.
 */

/**
 * Break a compound command into simple-command segments on the shell control
 * operators, so a bare executable anywhere in the chain (piped, chained, or
 * in a subshell) is inspected as its own leading command.
 */
export function splitSegments(command: string): string[] {
	return command.split(/\|\||&&|;|\||&|\r?\n|\(|\)/);
}

/**
 * Leading tokens that mean "the real executable follows": common wrappers a
 * command may be delegated through. `sudo python`, `env FOO=bar python`,
 * `time python`, and friends must resolve to `python`.
 *
 * The bare backslash is the shell quoting escape; it is skipped as a wrapper
 * for parity with the Cursor-host implementation.
 */
export const WRAPPERS: ReadonlySet<string> = new Set([
	"sudo",
	"env",
	"time",
	"nice",
	"command",
	"exec",
	"builtin",
	"\\",
]);

/** Inline environment assignment: `VAR=value` (or `FOO=bar baz=qux cmd ...`). */
const INLINE_ASSIGNMENT = /^[A-Za-z_][A-Za-z0-9_]*=/;

/**
 * Resolve the leading executable of one segment.
 *
 * Skips inline `VAR=value` assignments and the wrapper commands in
 * {@link WRAPPERS}; returns the first remaining token, or `null` when the
 * segment is only assignments/wrappers (or empty).
 */
export function leadingExecutable(segment: string): string | null {
	const tokens = segment.split(/\s+/).filter((token) => token !== "");
	let i = 0;
	while (i < tokens.length) {
		const token = tokens[i];
		if (INLINE_ASSIGNMENT.test(token)) {
			i++; // inline environment assignment (VAR=value)
			continue;
		}
		if (WRAPPERS.has(token)) {
			i++; // wrapper command; the real executable follows
			continue;
		}
		break;
	}
	return i < tokens.length ? tokens[i] : null;
}

/**
 * Normalize an executable to a comparable basename: strip any directory path
 * (POSIX `/` or Windows `\`) and a trailing `.exe` (case-insensitive).
 */
export function basename(executable: string): string {
	const leaf = executable.replace(/.*[\\/]/, ""); // strip any directory path
	return leaf.replace(/\.exe$/i, ""); // strip a Windows .exe suffix
}
