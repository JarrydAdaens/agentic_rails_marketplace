// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * claude-as-review-bot-guardrail (pi host)
 *
 * A wrap-up review gate. When the agent settles — `agent_settled`, the only
 * event that means "pi will NOT continue on its own" — an external, read-only
 * Claude Opus session reviews this session's changes and returns either
 * `APPROVE` or `REJECT` plus at most three one-line issues. On REJECT the
 * capped review is fed back with `pi.sendUserMessage` so the agent can act on
 * it; on APPROVE the operator gets a `ctx.ui.notify` only and the local model
 * spends ZERO context on the outcome.
 *
 * WHY `agent_settled` AND NOT `agent_end`: after `agent_end` pi may still
 * auto-retry, auto-compact, or run queued follow-ups. `agent_settled` is the
 * point past which pi will not continue by itself.
 *
 * THREE MEASURED-ON-LIVE-PI FACTS THIS FILE IS BUILT AROUND (see
 * context/pi-agentic-ide/pi-agentic-ide.md §9.6 and §9.7; they are not
 * theory, a probe produced these results against pi 0.84.2):
 *
 *  1. `agent_settled` IS REENTRANT. Injecting a message from the handler
 *     starts another agent run, which settles again, which fires the handler
 *     again. The probe produced three full agent runs and stopped ONLY because
 *     a hard counter stopped it. The hard per-session cycle counter below
 *     (default maxCycles 2) is therefore the PRIMARY and ONLY load-bearing
 *     loop guard.
 *
 *  2. There is deliberately NO in-flight boolean and NO `ctx.isIdle()` check
 *     in this file. Both were measured returning the non-blocking value on
 *     every reentrant fire: `inFlight` read `false` (because
 *     `sendUserMessage` resolves as soon as the message is QUEUED, long
 *     before the run it triggers completes) and `ctx.isIdle()` read `true` on
 *     every fire, including the reentrant ones. The fingerprint check below
 *     is a SECONDARY guard that catches the unchanged-tree case and NOTHING
 *     else — if the agent edits files each cycle the fingerprint differs every
 *     time and it stops nothing. The counter is what stops the loop.
 *
 *  3. In PRINT MODE the mechanism does not work at all: under `pi -p` the
 *     handler fires once, the injected message never runs, and the deferred
 *     call throws "This extension ctx is stale after session replacement or
 *     reload." The handler therefore RETURNS IMMEDIATELY when
 *     `ctx.mode === "print"` — standing down silently, without error.
 *
 * Review failures are classified with the shared advisor-failure module: a
 * HARD failure (authentication, quota/credits, model availability — or the
 * CLI being unreachable, which is itself classified hard) means SKIP the
 * review entirely and notify; it never wedges and never burns more cycles.
 * A SOFT failure may be retried once WITHIN the cycle budget.
 *
 * The operator is running a 131k-context local model, so every byte is
 * rationed: the diff in the review prompt is byte-capped (default 60,000
 * bytes) and the truncation is said plainly in the prompt; the reviewer is
 * asked for a small fixed shape; and the whole reply is hard-capped
 * (default 2,000 characters) before anything is injected.
 *
 * Fail-safe: the handler body is fully wrapped; an internal error must never
 * break the session. The reviewer command line is the verified advisor set:
 * `claude -p --model opus --effort high --permission-mode plan
 * --tools Read,Grep,Glob --safe-mode --no-session-persistence
 * --output-format text`.
 *
 * Known limitations (also in the README): print mode cannot host this
 * guardrail at all (§9.7), and like every other host in this repository the
 * structured write tools are what get reviewed at settle time — shell
 * redirects are not intercepted.
 */

import { createHash } from "node:crypto";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { classifyAdvisorFailure, hardFailureCategory } from "../../shared/advisor-failure.ts";
import { capToBudget } from "../../shared/budget.ts";
import { resolveCli } from "../../shared/cli-resolution.ts";
import { isEnabled, loadHarnessConfig } from "../../shared/harness-config.ts";
import { runExternal } from "../../shared/run-external.ts";

export const GUARDRAIL_NAME = "claude-as-review-bot-guardrail";

// --- config ------------------------------------------------------------------

/** Config shape: `harness/claude-as-review-bot-guardrail/config.json`. */
export interface ReviewBotConfig {
	enabled?: boolean;
	/**
	 * HARD per-session review cycle budget. Default 2. This is the primary
	 * and only load-bearing loop guard — see the reentrancy note at the top
	 * of this file. A soft failure may be retried once within a cycle; each
	 * cycle costs at most one `sendUserMessage` injection.
	 */
	maxCycles?: number;
	/** Byte cap on the diff carried in the review prompt. Default 60000. */
	diffBudgetBytes?: number;
	/** Hard character cap on the reviewer reply before it is injected. Default 2000. */
	reviewBudgetChars?: number;
	/** Reviewer CLI timeout in seconds. Default 300. */
	timeoutSeconds?: number;
}

export const DEFAULT_MAX_CYCLES = 2;
export const DEFAULT_DIFF_BUDGET_BYTES = 60_000;
export const DEFAULT_REVIEW_BUDGET_CHARS = 2_000;
export const DEFAULT_TIMEOUT_SECONDS = 300;

function positiveInt(value: unknown, fallback: number): number {
	if (typeof value === "number" && Number.isFinite(value) && value > 0) {
		return Math.floor(value);
	}
	return fallback;
}

export function configMaxCycles(config: ReviewBotConfig | null): number {
	return positiveInt(config?.maxCycles, DEFAULT_MAX_CYCLES);
}

export function configDiffBudgetBytes(config: ReviewBotConfig | null): number {
	return positiveInt(config?.diffBudgetBytes, DEFAULT_DIFF_BUDGET_BYTES);
}

export function configReviewBudgetChars(config: ReviewBotConfig | null): number {
	return positiveInt(config?.reviewBudgetChars, DEFAULT_REVIEW_BUDGET_CHARS);
}

export function configTimeoutSeconds(config: ReviewBotConfig | null): number {
	return positiveInt(config?.timeoutSeconds, DEFAULT_TIMEOUT_SECONDS);
}

// --- the reviewer command line (verified advisor set) --------------------------

/**
 * The Claude reviewer flag set, exactly the verified advisor command line:
 * latest Opus alias, high effort, read-only plan mode, only Read/Grep/Glob,
 * safe mode, no session persistence, plain text out. Appended after the
 * resolved CLI's argv prefix.
 */
export const CLAUDE_REVIEW_FLAGS: readonly string[] = [
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
];

// --- git state ------------------------------------------------------------------

export interface GitState {
	/** False when the cwd is not inside a git working tree. */
	isRepo: boolean;
	/** True when there are changed, staged, or untracked files to review. */
	hasChanges: boolean;
	/** One entry per `git status --porcelain` line. */
	files: string[];
	/** Raw `git status --porcelain` output. */
	status: string;
	/** `git diff HEAD` output (unstaged and staged tracked changes). */
	diff: string;
	/** The project root the commands ran in. */
	cwd: string;
}

/**
 * Fingerprint the review state. A pure function of the status and the diff:
 * equal states produce equal fingerprints, different states (almost always)
 * do not. This is the SECONDARY guard only — it catches the unchanged-tree
 * case, and nothing else.
 */
export function computeFingerprint(status: string, diff: string): string {
	return createHash("sha256").update(`${status}\n---\n${diff}`, "utf8").digest("hex");
}

export type GitExecutor = (cwd: string) => Promise<GitState>;

/** The `exec` member of pi's ExtensionAPI, structured so tests can fake it. */
export interface GitExecution {
	exec(
		command: string,
		args: string[],
		options?: { cwd?: string; timeout?: number; signal?: AbortSignal },
	): Promise<{ stdout: string; stderr: string; code: number }>;
}

/** Git subprocess cap: these are cheap local commands; a hang is a skip, not a wedge. */
const GIT_TIMEOUT_MS = 30_000;
/** Bound in-memory diff before the byte cap is applied (the prompt cap is much lower). */
const MAX_RAW_DIFF_CHARS = 2_000_000;

/**
 * Parse `git status --porcelain` output into file entries. Each line is
 * `<XY> <path>` (two status characters, a space, the path; renames carry an
 * arrow in the path). Short or malformed lines fall back to their trimmed
 * form rather than losing data.
 */
export function parseStatusFiles(status: string): string[] {
	return status
		.split("\n")
		.map((line) => (line.length >= 4 ? line.slice(3).trim() : line.trim()))
		.filter((entry) => entry !== "");
}

/**
 * Build a `GitExecutor` on top of `pi.exec`. A missing git binary, a
 * non-repository cwd, or a hung git all resolve to a GitState that makes the
 * guardrail skip — they never throw out of the handler.
 */
export function makeGitExecutor(execSource: GitExecution): GitExecutor {
	return async (cwd: string): Promise<GitState> => {
		const git = (args: string[]): Promise<{ ok: boolean; stdout: string; stderr: string }> =>
			execSource
				.exec("git", args, { cwd, timeout: GIT_TIMEOUT_MS })
				.then((result) => ({ ok: result.code === 0, stdout: result.stdout, stderr: result.stderr }));

		const inside = await git(["rev-parse", "--is-inside-work-tree"]);
		if (!inside.ok || inside.stdout.trim() !== "true") {
			return { isRepo: false, hasChanges: false, files: [], status: "", diff: "", cwd };
		}

		const status = await git(["status", "--porcelain"]);
		if (!status.ok) {
			return { isRepo: true, hasChanges: false, files: [], status: "", diff: "", cwd };
		}

		const diff = await git(["diff", "HEAD"]);
		const statusText = status.stdout;
		const files = parseStatusFiles(statusText);
		const diffText = diff.ok ? diff.stdout.slice(0, MAX_RAW_DIFF_CHARS) : "";

		return {
			isRepo: true,
			hasChanges: statusText.trim() !== "" || diffText.trim() !== "",
			files,
			status: statusText,
			diff: diffText,
			cwd,
		};
	};
}

// --- the bounded review input ----------------------------------------------------

export interface CappedDiff {
	diff: string;
	truncated: boolean;
	/** Bytes that were omitted by the cap (0 when it fit). */
	omittedBytes: number;
}

/**
 * Byte-cap a diff without ever splitting a multi-byte character: the diff is
 * cut on a line boundary, so the result is always valid UTF-8 and never
 * longer than `budgetBytes` bytes. A zero budget yields an empty diff.
 */
export function capDiffToBytes(diff: string, budgetBytes: number): CappedDiff {
	const budget = positiveInt(budgetBytes, DEFAULT_DIFF_BUDGET_BYTES);
	const totalBytes = Buffer.byteLength(diff, "utf8");
	if (totalBytes <= budget) {
		return { diff, truncated: false, omittedBytes: 0 };
	}
	const lines = diff.split("\n");
	const kept: string[] = [];
	let keptBytes = 0;
	for (const line of lines) {
		const lineBytes = Buffer.byteLength(line, "utf8") + 1; // + newline
		if (keptBytes + lineBytes > budget) {
			break;
		}
		kept.push(line);
		keptBytes += lineBytes;
	}
	return {
		diff: kept.join("\n"),
		truncated: true,
		omittedBytes: totalBytes - keptBytes,
	};
}

/**
 * Build the review prompt: changed-file list + byte-capped diff + the small
 * fixed reply shape. When the diff was truncated, the prompt says so plainly
 * so the reviewer does not assume it saw everything.
 */
export function buildReviewPrompt(gitState: GitState, config: ReviewBotConfig | null): string {
	const budget = configDiffBudgetBytes(config);
	const capped = capDiffToBytes(gitState.diff, budget);
	const fileList =
		gitState.files.length > 0 ? gitState.files.map((file) => `- ${file}`).join("\n") : "(no status lines)";
	const diffSection = capped.diff !== "" ? capped.diff : "(no diff produced)";
	const truncation = capped.truncated
		? `The diff above was TRUNCATED to ${budget} bytes (${capped.omittedBytes} bytes omitted). You did not see the complete change; do not approve code you did not see, and say so in any issue that depends on it.`
		: "The diff above is complete: it fit within the byte budget.";

	return (
		"You are a strict code reviewer for a coding agent that has just finished a change in the repository. " +
		"Review the changes for correctness, scope, and obvious mistakes. Do not implement or modify files.\n\n" +
		`Files changed:\n${fileList}\n\n` +
		`Diff (git diff HEAD):\n${diffSection}\n\n` +
		`${truncation}\n\n` +
		`Answer in this exact shape and nothing else:\n` +
		`Line 1: APPROVE or REJECT — the single word, nothing else on the line.\n` +
		`Then, only if REJECT: at most three issues. Each issue is exactly two lines: one line of problem, one line of the fix.\n` +
		`Your entire reply must stay under ${configReviewBudgetChars(config)} characters. No preamble.`
	);
}

// --- verdict parsing ---------------------------------------------------------------

export interface ParsedVerdict {
	verdict: "APPROVE" | "REJECT";
	/** Everything after the verdict line, trimmed. */
	body: string;
}

/**
 * Parse the reviewer reply. THE FIRST NON-EMPTY LINE must be exactly the
 * single word `APPROVE` or `REJECT` — anything else on that line, or a
 * missing verdict, is a malformed reply (`null`). Malformed is a SOFT
 * condition: the caller may retry within the cycle budget.
 */
export function parseVerdict(reply: string): ParsedVerdict | null {
	const lines = (reply ?? "").replace(/\r\n/g, "\n").split("\n");
	let index = -1;
	for (let i = 0; i < lines.length; i++) {
		const trimmed = lines[i].trim();
		if (trimmed !== "") {
			index = i;
			break;
		}
	}
	if (index === -1) {
		return null; // empty reply
	}
	const first = lines[index].trim();
	if (first !== "APPROVE" && first !== "REJECT") {
		return null; // malformed: the verdict is not the single word on line one
	}
	return {
		verdict: first,
		body: lines.slice(index + 1).join("\n").trim(),
	};
}

// --- the review cycle (pure: injectable runner, testable without any CLI) ----------

/** A failed reviewer round: HARD (skip entirely) or SOFT (retry within budget). */
export interface ReviewError {
	reason: "hard" | "soft";
	error: string;
}

export type ReviewOutcome =
	| { outcome: "approved"; attempts: number }
	| { outcome: "rejected"; review: string; attempts: number }
	| (ReviewError & { outcome: "failed"; attempts: number });

/** Session-scoped review state. The counter is per session, in memory. */
export interface ReviewState {
	/** Review cycles spent this session (primary loop guard). */
	cyclesUsed: number;
	/** Fingerprints already reviewed this session (secondary guard). */
	reviewedFingerprints: Set<string>;
}

export function createReviewState(): ReviewState {
	return { cyclesUsed: 0, reviewedFingerprints: new Set() };
}

export interface CycleDecision {
	allowed: boolean;
	maxCycles: number;
}

/**
 * The HARD per-session cycle counter — the primary and only load-bearing
 * loop guard. `agent_settled` is reentrant and neither an in-flight boolean
 * nor `ctx.isIdle()` can see it (both measured, §9.6), so nothing about
 * "is a run in flight" is consulted here.
 */
export function decideCycle(state: ReviewState, config: ReviewBotConfig | null): CycleDecision {
	const maxCycles = configMaxCycles(config);
	return { allowed: state.cyclesUsed < maxCycles, maxCycles };
}

/** Secondary guard: never re-review a change set this session already reviewed. */
export function recordFingerprint(state: ReviewState, fingerprint: string): void {
	state.reviewedFingerprints.add(fingerprint);
}

export function hasReviewedFingerprint(state: ReviewState, fingerprint: string): boolean {
	return state.reviewedFingerprints.has(fingerprint);
}

export interface ReviewRunnerOptions {
	timeoutSeconds: number;
	cwd: string;
	signal: AbortSignal | null;
	/** 1-based attempt within the cycle (soft retries stay inside one cycle). */
	attempt: number;
}

/**
 * The reviewer transport. Production wraps shared/run-external.ts; tests
 * inject a fake. A rejection (throw) means the review round failed — the
 * message is classified by shared/advisor-failure.ts, where "not found"
 * makes an unreachable CLI a HARD failure (skip, do not retry forever).
 */
export type ReviewRunner = (prompt: string, options: ReviewRunnerOptions) => Promise<string> | string;

/**
 * Run one review cycle against an injectable runner.
 *
 * - The prompt is built from the bounded review input (byte-capped diff,
 *   truncation said plainly).
 * - A HARD failure (authentication, quota/credits, model availability, CLI
 *   unreachable) returns `failed`/`hard` immediately: SKIP the review
 *   entirely, never wedge, never burn the rest of the cycle budget.
 * - A SOFT failure (transient, or a malformed reply) is retried up to
 *   `maxCycles` times WITHIN this one cycle — the per-session counter is
 *   still the thing that bounds the outer loop.
 * - On REJECT the reply is hard-capped to `reviewBudgetChars` before it is
 *   returned for injection; a REJECT with no body is malformed and retried.
 */
export async function runReview(
	config: ReviewBotConfig | null,
	gitState: GitState,
	runner: ReviewRunner,
	signal: AbortSignal | null = null,
): Promise<ReviewOutcome> {
	const prompt = buildReviewPrompt(gitState, config);
	const attemptsAllowed = Math.max(1, configMaxCycles(config));
	let lastError: string | null = null;

	for (let attempt = 1; attempt <= attemptsAllowed; attempt++) {
		let reply = "";
		try {
			reply = await runner(prompt, {
				timeoutSeconds: configTimeoutSeconds(config),
				cwd: gitState.cwd,
				signal,
				attempt,
			});
		} catch (err) {
			const detail = err instanceof Error ? err.message : String(err);
			if (classifyAdvisorFailure(detail) === "hard") {
				return { outcome: "failed", reason: "hard", error: detail, attempts: attempt };
			}
			lastError = detail; // SOFT: retry within the cycle budget
			continue;
		}

		const parsed = parseVerdict(reply);
		if (parsed === null) {
			lastError = "the reviewer did not return a single-word APPROVE or REJECT on the first line";
			continue;
		}

		if (parsed.verdict === "APPROVE") {
			return { outcome: "approved", attempts: attempt };
		}

		const body = parsed.body;
		if (body === "") {
			lastError = "the reviewer returned REJECT but no issues to act on";
			continue;
		}

		// CAP the reply hard before it can reach the 131k-context model.
		return {
			outcome: "rejected",
			review: capToBudget(body, configReviewBudgetChars(config)),
			attempts: attempt,
		};
	}

	return {
		outcome: "failed",
		reason: "soft",
		error: lastError ?? "the reviewer could not be reached",
		attempts: attemptsAllowed,
	};
}

// --- messages ---------------------------------------------------------------------

/** The message fed back to the agent on REJECT (already capped). */
export function rejectionMessage(review: string, cyclesUsed: number, maxCycles: number): string {
	const budgetNote =
		cyclesUsed >= maxCycles
			? " This is the last review cycle for this session; act on it fully."
			: ` (${maxCycles - cyclesUsed} review cycle(s) remain this session.)`;
	return (
		`claude-as-review-bot-guardrail: the external reviewer REJECTed this session's change set.${budgetNote}\n\n` +
		`${review}\n\n` +
		`Remediate the issue(s) above, then finish. The reviewer saw only the diff it was given.`
	);
}

/** The operator notification when the review is skipped (hard) or could not complete (soft). */
export function skippedReviewerMessage(outcome: Extract<ReviewOutcome, { outcome: "failed" }>): string {
	const detail = (outcome.error ?? "").trim() !== "" ? (outcome.error ?? "").trim() : "No error message was returned.";
	if (outcome.reason === "hard") {
		const category = hardFailureCategory(detail);
		const why = category ? ` (likely ${category})` : "";
		return (
			`claude-as-review-bot-guardrail: the external reviewer is unavailable${why}: ${detail} The review was ` +
			`skipped entirely and the session stands down — an unusable reviewer must never wedge or loop. ` +
			`Fix the cause (sign in, restore quota or credits, choose an available model), or set ` +
			`harness/${GUARDRAIL_NAME}/config.json to {"enabled": false} to silence this guardrail.`
		);
	}
	return (
		`claude-as-review-bot-guardrail: the external review could not be completed after ` +
		`${outcome.attempts} attempt(s): ${detail} The review was skipped and the change set is left as-is; ` +
		`this session's remaining review cycles are not re-spent on it automatically.`
	);
}

// --- the settled handler (pi glue) ---------------------------------------------------

/**
 * `ctx.ui.notify`, when the context has a UI. Always guarded: `ctx.hasUI` is
 * false in print/RPC mode, and a notify failure must never surface.
 */
function safeNotify(ctx: unknown, message: string, type: "info" | "warning" = "info"): void {
	const context = ctx as
		| { hasUI?: unknown; ui?: { notify?: (message: string, type?: "info" | "warning" | "error") => void } }
		| null
		| undefined;
	if (!context || context.hasUI === false || typeof context.ui?.notify !== "function") {
		return;
	}
	try {
		context.ui?.notify?.(message, type);
	} catch {
		// A notify failure is cosmetic; swallow it, never break the session.
	}
}

/**
 * The production reviewer: the verified Claude flag set through the shared
 * runner. Throws on every failure so runReview can classify it — never
 * swallows.
 */
export function makeProductionRunner(): ReviewRunner {
	return async (_prompt, options) => {
		const cli = resolveCli("claude");
		if (!cli.found) {
			// "not found" is a HARD failure: classified, skipped, no retry loop.
			throw new Error(`claude CLI unavailable: ${cli.note ?? "not found"}`);
		}
		const result = await runExternal([...(cli.argvPrefix ?? []), ...CLAUDE_REVIEW_FLAGS], _prompt, {
			timeoutSeconds: options.timeoutSeconds,
			signal: options.signal,
			cwd: options.cwd,
		});
		if (result.status === "timedout") {
			throw new Error(result.note ?? "the reviewer CLI timed out.");
		}
		if (result.status !== "ok") {
			const detail = [result.stderr, result.stdout]
				.map((stream) => stream.trim())
				.filter((stream) => stream !== "")
				.join(" ");
			throw new Error(detail !== "" ? detail : (result.note ?? "the reviewer CLI exited non-zero."));
		}
		return result.stdout;
	};
}

/**
 * The full `agent_settled` pass. Pure glue around the exported pieces so
 * tests can drive it with a fake git executor and fake runner — no test ever
 * spawns the real claude CLI. Returns a short reason string (for the
 * operator / tests); throws nothing.
 */
export async function runSettledReview(
	ctx: unknown,
	state: ReviewState,
	gitExecutor: GitExecutor,
	sendUserMessage: (message: string) => void,
	runner: ReviewRunner,
): Promise<string> {
	// MEASURED (§9.7): under `pi -p` this handler fires once, the injected
	// message never runs, and the deferred send throws "This extension ctx is
	// stale after session replacement or reload." Stand down silently.
	const context = ctx as { mode?: unknown } | null | undefined;
	if (context?.mode === "print") {
		return "stand-down: print mode cannot host a wrap-up review";
	}

	const cwdRaw = (ctx as { cwd?: unknown } | null | undefined)?.cwd;
	const cwd = typeof cwdRaw === "string" && cwdRaw !== "" ? cwdRaw : process.cwd();

	const config = loadHarnessConfig(cwd, GUARDRAIL_NAME) as ReviewBotConfig | null;
	if (!isEnabled(config)) {
		return "stand-down: disabled by project config";
	}

	const git = await gitExecutor(cwd);
	if (!git.isRepo) {
		return "skipped: not a git repository";
	}
	if (!git.hasChanges) {
		return "skipped: no changes to review";
	}

	const fingerprint = computeFingerprint(git.status, git.diff);
	if (hasReviewedFingerprint(state, fingerprint)) {
		safeNotify(
			ctx,
			`claude-as-review-bot-guardrail: this change set was already reviewed this session; standing down.`,
			"info",
		);
		return "skipped: already reviewed this session";
	}

	// THE HARD COUNTER — primary and only load-bearing loop guard (§9.6).
	const decision = decideCycle(state, config);
	if (!decision.allowed) {
		safeNotify(
			ctx,
			`claude-as-review-bot-guardrail: the per-session review budget (${decision.maxCycles} cycle(s)) is ` +
				`spent. I am standing down so the review cannot loop; a human should take it from here.`,
			"warning",
		);
		return "skipped: per-session cycle budget spent";
	}
	state.cyclesUsed += 1;

	const signal = (ctx as { signal?: unknown } | null | undefined)?.signal;
	const outcome = await runReview(config, git, runner, signal instanceof AbortSignal ? signal : null);
	recordFingerprint(state, fingerprint);

	if (outcome.outcome === "approved") {
		// APPROVE costs the local model ZERO context: notify only.
		safeNotify(
			ctx,
			`claude-as-review-bot-guardrail: the external reviewer APPROVED this session's change set. Nothing to do.`,
			"info",
		);
		return "reviewed: approved";
	}

	if (outcome.outcome === "rejected") {
		const message = rejectionMessage(outcome.review, state.cyclesUsed, decision.maxCycles);
		try {
			// Injecting THIS message starts another agent run, which settles
			// again — the counter above is the only thing that bounds that.
			sendUserMessage(message);
		} catch (err) {
			const detail = err instanceof Error ? err.message : String(err);
			safeNotify(
				ctx,
				`claude-as-review-bot-guardrail: the reviewer REJECTed, but the feedback could not be delivered ` +
					`(${detail}). The rejection is: ${outcome.review}`,
				"warning",
			);
			return "reviewed: rejected (feedback undelivered)";
		}
		safeNotify(
			ctx,
			`claude-as-review-bot-guardrail: the external reviewer REJECTed the change set; remediation was sent ` +
				`back to the agent.`,
			"warning",
		);
		return "reviewed: rejected";
	}

	// failed: hard (skip entirely) or soft (in-cycle retries exhausted).
	safeNotify(ctx, skippedReviewerMessage(outcome), "warning");
	return outcome.reason === "hard"
		? "skipped: reviewer unavailable (hard failure)"
		: "failed: reviewer retries exhausted (soft)";
}

// --- extension entry point -------------------------------------------------------------

/**
 * The extension. One event subscription, no tools, no markers: state is
 * in-memory per session, which pi's in-process model makes sufficient.
 */
export default function (pi: ExtensionAPI) {
	const state = createReviewState();
	const gitExecutor = makeGitExecutor(pi);
	const runner = makeProductionRunner();

	pi.on("agent_settled", (_event, ctx) => {
		// Fail-safe: an internal error must NEVER break the session, and this
		// handler runs when pi believes it is done — a throw here is the last
		// thing the operator sees. runSettledReview swallows everything; the
		// catch is belt and braces.
		void runSettledReview(
			ctx,
			state,
			gitExecutor,
			(message) => {
				pi.sendUserMessage(message);
			},
			runner,
		).catch(() => {
			// suppressed on purpose: never break the session on settle
		});
	});
}
