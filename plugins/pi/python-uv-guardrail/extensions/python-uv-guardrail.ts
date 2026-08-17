// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * python-uv-guardrail (pi host)
 *
 * Deterministic "python only runs under uv" guardrail. A `tool_call` handler
 * on `bash` inspects every command before it runs and blocks any that invoke
 * a Python interpreter or installer directly — `python`, `python3`, `pip`,
 * `pip3`, or the Windows `py` launcher — instead of through `uv`. It spends
 * no LLM judgment: the decision is a pure pattern match.
 *
 * This is a port of the decision logic in
 * plugins/cursor/python-uv-guardrail/hooks/enforce-uv-python.ps1. The stdin
 * reading, BOM stripping, and JSON response envelope of the PowerShell hook
 * are deliberately NOT ported: pi hooks are in-process and need none of that
 * transport.
 *
 * It blocks with `{ block: true, reason }` and does NOT terminate, because a
 * legitimate remedy exists — the deny message names it and the agent can
 * reach it. (`terminate: true` is reserved for prohibitions with no remedy,
 * like `git push`; the spike showed that pairing a block-with-remedy with
 * terminate-less messaging and getting it wrong sends a local model into a
 * retry loop. See plan Evidence 9.2: a naive guardrail blocked `uv run
 * python --version`, the exact remedy its own message recommended.)
 *
 * Fail open: every handler body is wrapped so an internal guardrail error
 * allows the bash tool through rather than blocking it. A guardrail bug must
 * never wedge the bash tool.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { basename, leadingExecutable, splitSegments } from "../../shared/bash-segments.ts";
import { isEnabled, loadHarnessConfig } from "../../shared/harness-config.ts";

export const GUARDRAIL_NAME = "python-uv-guardrail";

/**
 * Interpreter/installer basenames that must be run under uv. `python`,
 * `python3`, `python3.12`, `pip`, `pip3`, and the Windows `py` launcher are
 * all pollution paths.
 */
export const DEFAULT_BLOCKED_PATTERN = "^(py|python(\\d+(\\.\\d+)?)?|pip\\d*)$";

/** Leading tokens that mean "this segment is already delegated to uv". */
export const UV_PREFIXES: ReadonlySet<string> = new Set(["uv", "uvx"]);

/**
 * Find the first segment in a compound command whose leading executable is a
 * blocked interpreter, or `null` if the command is clean.
 *
 * Segment-aware, not a flat regex: pipes, chains, subshells, inline
 * assignments, and wrapper commands are handled per segment, and a segment
 * led by `uv`/`uvx` is exempt — including `uv run python ...`, which is the
 * remedy the deny message itself recommends.
 */
export function findBareInterpreter(
	command: string,
	blockedPattern: string = DEFAULT_BLOCKED_PATTERN,
): string | null {
	const pattern = new RegExp(blockedPattern, "i");
	for (const segment of splitSegments(command)) {
		const executable = leadingExecutable(segment);
		if (executable === null) {
			continue;
		}
		if (UV_PREFIXES.has(executable.toLowerCase())) {
			continue; // already delegated to uv
		}
		if (pattern.test(basename(executable))) {
			return executable;
		}
	}
	return null;
}

/** Config shape: `harness/python-uv-guardrail/config.json`. */
export interface PythonUvConfig {
	enabled?: boolean;
	blockedPattern?: string;
	allowCommands?: string[];
}

export interface PythonUvDecision {
	blocked: boolean;
	offender: string | null;
}

/**
 * The full deny decision for one command against an optional project config.
 *
 * Absent/empty/malformed config means "enforce with defaults";
 * `"enabled": false` stands the guardrail down; `blockedPattern` and
 * `allowCommands` (case-insensitive regexes against the whole command)
 * override the defaults.
 */
export function decide(
	command: string,
	config: PythonUvConfig | null = null,
): PythonUvDecision {
	if (!isEnabled(config)) {
		return { blocked: false, offender: null };
	}

	const allowCommands = config?.allowCommands;
	if (Array.isArray(allowCommands)) {
		for (const pattern of allowCommands) {
			if (
				typeof pattern === "string" &&
				pattern.trim() !== "" &&
				new RegExp(pattern, "i").test(command)
			) {
				return { blocked: false, offender: null }; // explicitly allowlisted by the project
			}
		}
	}

	const configured = config?.blockedPattern;
	const blockedPattern =
		typeof configured === "string" && configured.trim() !== ""
			? configured
			: DEFAULT_BLOCKED_PATTERN;

	const offender = findBareInterpreter(command, blockedPattern);
	return { blocked: offender !== null, offender };
}

/** The deny text. Ported verbatim from the Cursor-host hook; the model acts on it. */
export function denyReason(offender: string): string {
	return (
		`python-uv-guardrail: '${offender}' was invoked directly, without uv. ` +
		`Re-run it through uv so it uses an isolated, project-scoped environment instead ` +
		`of mutating a shared global interpreter. For example: 'uv run python <args>', ` +
		`'uv run <script>.py', 'uv pip install <pkg>', or 'uvx <tool>'. Then retry.`
	);
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", (event, ctx) => {
		// Fail open: any internal error here allows the bash tool through.
		// A guardrail bug must never wedge the bash tool.
		try {
			if (event.toolName !== "bash") {
				return undefined;
			}
			const command = (event.input as { command?: unknown } | undefined)?.command;
			if (typeof command !== "string" || command.trim() === "") {
				return undefined; // nothing to inspect
			}

			const projectRoot =
				typeof ctx?.cwd === "string" && ctx.cwd !== "" ? ctx.cwd : process.cwd();
			const config = loadHarnessConfig(
				projectRoot,
				GUARDRAIL_NAME,
			) as PythonUvConfig | null;

			const decision = decide(command, config);
			if (!decision.blocked || decision.offender === null) {
				return undefined;
			}
			// Block, but do NOT terminate: a legitimate remedy exists, and the
			// reason below names it.
			return { block: true, reason: denyReason(decision.offender) };
		} catch {
			return undefined; // internal error: fail open
		}
	});
}
