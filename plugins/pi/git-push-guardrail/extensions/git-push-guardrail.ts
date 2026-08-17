// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * git-push-guardrail (pi host)
 *
 * Agents in this repository never push to a remote — publishing is a
 * deliberate, human-only act. A `tool_call` handler on `bash` inspects every
 * command before it runs and blocks any segment whose leading executable is
 * `git` and whose arguments contain `push`, wherever it sits in the chain —
 * `git push`, `git push --force`, `git -C /some/dir push`, `x && git push`.
 * No LLM judgment: the decision is a pure pattern match, segment-aware.
 *
 * This guardrail has no Cursor-host sibling to port from; it is new. It
 * reuses the shared shell-command segmentation so a push hidden behind a
 * chain is caught the same way `python` is in python-uv-guardrail.
 *
 * It blocks with `{ block: true, reason, terminate: true }` — the opposite
 * of its remedy-carrying siblings, because there is NO legitimate remedy an
 * agent may reach: the human pushes from their own terminal. `terminate` is
 * what matters: the spike (plan Evidence 9.3) measured that terminating
 * stops the local model's retry loop, and that a block-without-terminate
 * sends it into six wasted tool calls fighting a prohibition.
 *
 * There is deliberately NO per-command allowlist: a regex escape hatch on a
 * hard prohibition is an accident waiting to happen. The only config key is
 * `enabled`.
 *
 * It must NOT hook `user_bash`: that event is the human typing `!git push`,
 * and restraining the human is not this guardrail's job.
 *
 * Fail open: every handler body is wrapped so an internal guardrail error
 * allows the bash tool through rather than blocking it. Pi's `tool_call`
 * fails CLOSED (an unhandled throw wedges the guarded tool for the session),
 * so this wrapping is mandatory, not stylistic.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { basename, splitSegments, WRAPPERS } from "../../shared/bash-segments.ts";
import { isEnabled, loadHarnessConfig } from "../../shared/harness-config.ts";

export const GUARDRAIL_NAME = "git-push-guardrail";

/** Config shape: `harness/git-push-guardrail/config.json`. `enabled` only. */
export interface GitPushConfig {
	enabled?: boolean;
}

/**
 * True when some segment of the command is `git ... push ...`: leading
 * executable `git` (directory and `.exe` stripped, inline assignments and
 * wrappers skipped) with a `push` subcommand argument.
 *
 * `echo "git push"` is clean (the segment is led by `echo`), and
 * `git commit -m "push it later"` is clean (`"push` is not the `push`
 * subcommand token) — a message that merely mentions push never fires.
 */
export function hasGitPush(command: string): boolean {
	for (const segment of splitSegments(command)) {
		const tokens = segment.split(/\s+/u).filter((token) => token !== "");
		let i = 0;
		while (i < tokens.length) {
			const token = tokens[i];
			if (/^[A-Za-z_][A-Za-z0-9_]*=/u.test(token)) {
				i++; // inline environment assignment (VAR=value)
				continue;
			}
			if (WRAPPERS.has(token)) {
				i++; // wrapper command; the real executable follows
				continue;
			}
			break;
		}
		if (i >= tokens.length || basename(tokens[i]) !== "git") {
			continue;
		}
		for (let j = i + 1; j < tokens.length; j++) {
			if (tokens[j].toLowerCase() === "push") {
				return true;
			}
		}
	}
	return false;
}

export interface GitPushDecision {
	blocked: boolean;
}

/**
 * The deny decision for one command against an optional project config.
 *
 * Absent/empty/malformed config means "enforce with defaults";
 * `"enabled": false` stands the guardrail down. There is no other key —
 * deliberately no per-command allowlist.
 */
export function decide(command: string, config: GitPushConfig | null = null): GitPushDecision {
	if (!isEnabled(config)) {
		return { blocked: false };
	}
	if (typeof command !== "string" || command.trim() === "") {
		return { blocked: false };
	}
	return { blocked: hasGitPush(command) };
}

/**
 * The deny text. It names the prohibition, the one legitimate path (a human,
 * a terminal), and says plainly that no alternate command reaches the same
 * effect — a local model reads that and stops instead of retrying variants.
 */
export function denyReason(): string {
	return (
		`git-push-guardrail: 'git push' is forbidden. Agents in this project never push to ` +
		`a remote: publishing is a deliberate, human-only act, and no alternate command ` +
		`reaches the same effect. Stop here, do not retry a variant, and ask the operator ` +
		`to push from their own terminal when they are ready.`
	);
}

// --- pi glue ------------------------------------------------------------------

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", (event, ctx) => {
		// Fail open: pi's tool_call fails CLOSED, so an internal guardrail error
		// must be swallowed to keep the bash tool usable. A guardrail bug must
		// never wedge bash.
		try {
			if (event.toolName !== "bash") {
				return undefined; // bash only — and never user_bash, which is the human
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
			) as GitPushConfig | null;

			if (!decide(command, config).blocked) {
				return undefined;
			}
			// Block AND terminate: there is no remedy an agent may reach, and
			// terminating is what stops the local model's retry loop.
			return { block: true, reason: denyReason(), terminate: true };
		} catch {
			return undefined; // internal error: fail open
		}
	});
}
