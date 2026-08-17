// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * claude-as-advisor-guardrail (pi host)
 *
 * A constructive, cross-vendor senior engineering advisor: a read-only Claude
 * Opus session consulted before substantive implementation, when stuck,
 * before a meaningful pivot, and before declaring completion.
 *
 * Pi has no MCP and needs none: `pi.registerTool()` exposes exactly ONE tool,
 * `consult_claude_advisor`, as the MCP replacement. That replaces the whole
 * shell-CLI-over-stdin protocol, protocol document, and marker-file dance the
 * Cursor and Codex hosts were forced into — the write gate just watches for
 * its own tool having succeeded, in in-memory state (pi extensions are
 * in-process, so there are no marker files to manage).
 *
 * The write gate: `tool_call` on `write`/`edit` is denied until one consult
 * has succeeded in this session. An unreachable advisor must never wedge the
 * session — if the Claude CLI cannot be resolved, a consult times out, or a
 * consult RUNS and fails with a HARD cause (authentication, quota/credits,
 * model availability — classified by shared/advisor-failure.ts), the gate
 * DISARMS: the advisor is unusable and must not deny every write. A SOFT
 * failure (anything else — transient, malformed, one-off) leaves the gate
 * armed: the model sees the failure and can fix the cause and retry.
 *
 * Fail open: every `tool_call` handler body is wrapped so an internal
 * guardrail error allows the guarded tool through rather than blocking it.
 * Pi's `tool_call` fails CLOSED (an unhandled throw wedges write and edit for
 * the session), so this wrapping is mandatory, not stylistic. Tool `execute`
 * errors are different: they are thrown, and pi reports them to the model
 * with `isError: true` and continues — advisor failures must never be
 * swallowed silently.
 *
 * Prompt shape and command line are ported from
 * plugins/cursor/claude-as-advisor-guardrail (advisor-protocol.md,
 * lib/advisor_consult.py). The reply is capped via budget.ts before it
 * reaches the 131k-context model.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { classifyAdvisorFailure, hardFailureCategory } from "../../shared/advisor-failure.ts";
import { capToBudget } from "../../shared/budget.ts";
import { resolveCli } from "../../shared/cli-resolution.ts";
import { isEnabled, loadHarnessConfig } from "../../shared/harness-config.ts";
import { runExternal } from "../../shared/run-external.ts";

export const GUARDRAIL_NAME = "claude-as-advisor-guardrail";

// --- config ------------------------------------------------------------------

/** Config shape: `harness/claude-as-advisor-guardrail/config.json`. */
export interface ClaudeAdvisorConfig {
	enabled?: boolean;
	/** Consult timeout in seconds. Default 600. */
	consult_timeout_seconds?: number;
	/** Character cap on the advisor reply before it reaches the model. Default 4000. */
	reply_budget_chars?: number;
}

/** Default consult timeout: 600 seconds. */
export const DEFAULT_TIMEOUT_SECONDS = 600;
/** Default reply cap: 4000 characters, enforced with budget.ts. */
export const DEFAULT_REPLY_BUDGET_CHARS = 4000;

export function configTimeoutSeconds(config: ClaudeAdvisorConfig | null): number {
	const value = config?.consult_timeout_seconds;
	return typeof value === "number" && Number.isFinite(value) && value > 0
		? Math.floor(value)
		: DEFAULT_TIMEOUT_SECONDS;
}

export function configReplyBudgetChars(config: ClaudeAdvisorConfig | null): number {
	const value = config?.reply_budget_chars;
	return typeof value === "number" && Number.isFinite(value) && value > 0
		? Math.floor(value)
		: DEFAULT_REPLY_BUDGET_CHARS;
}

// --- consult arguments --------------------------------------------------------

/** Valid stages, matching the Cursor-host protocol. */
export const VALID_STAGES = ["planning", "stuck", "pivot-check", "completion-review"] as const;

export interface ConsultValues {
	task: string;
	stage: string;
	approach: string;
	evidence: string;
	question: string;
}

const CONSULT_FIELDS: readonly string[] = ["task", "stage", "approach", "evidence", "question"];

/**
 * Validate and normalize consult arguments (ported from
 * `advisor_consult.py:validate`). All five fields must be non-empty strings
 * and `stage` must be a valid stage.
 */
export function validateConsult(params: unknown): { values: ConsultValues | null; error: string | null } {
	if (typeof params !== "object" || params === null || Array.isArray(params)) {
		return {
			values: null,
			error:
				"consult_claude_advisor arguments must be an object with task, stage, " +
				"approach, evidence, and question.",
		};
	}
	const record = params as Record<string, unknown>;
	const missing: string[] = [];
	for (const field of CONSULT_FIELDS) {
		const value = record[field];
		if (typeof value !== "string" || value.trim() === "") {
			missing.push(field);
		}
	}
	if (missing.length > 0) {
		return {
			values: null,
			error: `missing or empty required field(s): ${missing.join(", ")}. All five fields must be non-empty strings.`,
		};
	}
	const stage = (record.stage as string).trim();
	if (!(VALID_STAGES as readonly string[]).includes(stage)) {
		return {
			values: null,
			error: `stage must be one of: ${VALID_STAGES.join(", ")}; received: ${stage}`,
		};
	}
	return {
		values: {
			task: (record.task as string).trim(),
			stage,
			approach: (record.approach as string).trim(),
			evidence: (record.evidence as string).trim(),
			question: (record.question as string).trim(),
		},
		error: null,
	};
}

/**
 * The advisor prompt, ported from `advisor_consult.py:build_prompt`. The
 * persona is constructive, not antagonistic: a plan, course correction, or
 * completion verdict, and every concern carries a forward path.
 */
export function buildPrompt(v: ConsultValues): string {
	const payload = [
		`TASK: ${v.task}`,
		`STAGE: ${v.stage}`,
		`PLAN/APPROACH: ${v.approach}`,
		`EVIDENCE: ${v.evidence}`,
		`QUESTION: ${v.question}`,
	].join("\n");
	return (
		"You are a constructive senior engineering advisor to a coding agent from another vendor. " +
		"Return a plan, course correction, or completion verdict. Do not implement or modify files. " +
		"Inspect files only to verify material claims.\n\n" +
		"Pair every concern with a forward path. Label speculation and name the cheap check that " +
		"settles it. If the executor is circling, give 2-4 alternatives in order. Recommending a stop " +
		"requires concrete evidence, the strongest case for continuing, and why no other work can proceed.\n\n" +
		"Otherwise answer in at most 120 words: one-sentence direction, 2-4 important decisions or " +
		"risks, and one verification. No preamble or restatement.\n\n" +
		`Structured consultation:\n${payload}\n`
	);
}

// --- the command line (verified) ----------------------------------------------

/**
 * The Claude advisor flag set, exactly as verified in the Cursor host
 * (`advisor_consult.py:command`): latest Opus alias, high effort, read-only
 * plan mode, only Read/Grep/Glob, safe mode, no session persistence, plain
 * text out. Appended after the resolved CLI's argv prefix.
 */
export const CLAUDE_ADVISOR_FLAGS: readonly string[] = [
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

// --- the write gate state machine ---------------------------------------------

/**
 * Session gate: `armed` denies writes until a consult succeeds (`satisfied`)
 * or the advisor proves unreachable/timed-out (`disarmed` — fail open, never
 * wedge the session).
 */
export type GateState = "armed" | "satisfied" | "disarmed";

export interface AdvisorGate {
	state: GateState;
}

export function createGate(): AdvisorGate {
	return { state: "armed" };
}

export function gateAllowsWrite(gate: AdvisorGate): boolean {
	return gate.state !== "armed";
}

export type ConsultOutcome =
	| { kind: "succeeded" }
	| { kind: "unreachable" }
	| { kind: "timedout" }
	| { kind: "hard_failed" }
	| { kind: "failed" };

/**
 * Apply a consult outcome to the gate.
 *
 * - succeeded   -> `satisfied` (writes allowed);
 * - unreachable, timedout, or hard_failed -> `disarmed` (writes allowed:
 *   an unreachable, hanging, or unusable advisor must never wedge the
 *   session — a hard failure such as authentication or an exhausted quota
 *   will fail identically on every retry);
 * - failed      -> unchanged. A SOFT failure (transient, malformed, one-off)
 *   must not silently open the gate; the model sees the failure, fixes the
 *   cause, and can retry.
 */
export function applyConsultOutcome(gate: AdvisorGate, outcome: ConsultOutcome): GateState {
	switch (outcome.kind) {
		case "succeeded":
			gate.state = "satisfied";
			break;
		case "unreachable":
		case "timedout":
		case "hard_failed":
			gate.state = "disarmed";
			break;
		case "failed":
			break; // unchanged, on purpose
	}
	return gate.state;
}

// --- messages -----------------------------------------------------------------

/** The write/edit deny text. The model acts on it; it names the remedy. */
export function denyReason(target: string | null): string {
	const what = target ? `the write of '${target}'` : "this write";
	return (
		`claude-as-advisor-guardrail: ${what} is denied because the advisor has not been ` +
		`consulted yet this session. This is expected behavior, not an error. Call the ` +
		`consult_claude_advisor tool with task, stage (planning, stuck, pivot-check, or ` +
		`completion-review), approach, evidence, and question, then retry the write.`
	);
}

export function unreachableAdvisorMessage(detail: string): string {
	return (
		`Claude advisor is unreachable: ${detail} The write gate is disarmed for this session. ` +
		`Install an authenticated claude CLI, or set harness/${GUARDRAIL_NAME}/config.json ` +
		`to {"enabled": false} to silence this guardrail.`
	);
}

export function timeoutAdvisorMessage(detail: string): string {
	return (
		`Claude advisor timed out.${detail ? ` ${detail}` : ""} The write gate is disarmed for ` +
		`this session. Narrow the evidence and try again, or raise consult_timeout_seconds.`
	);
}

/** SOFT failure: reported to the model, gate stays armed (retry is meaningful). */
export function failedAdvisorMessage(stderr: string, note: string | undefined): string {
	const detail = stderr.trim() !== "" ? ` ${stderr.trim()}` : note ? ` ${note}` : " No error message was returned.";
	return `Claude advisor failed (transient).${detail} The write gate stays armed: fix the cause and consult again.`;
}

/**
 * HARD failure (authentication, quota/credits, model availability): the
 * advisor is unusable, so the gate DISARMS instead of wedging the session.
 * The failure is still reported — never swallowed.
 */
export function hardFailureMessage(detail: string): string {
	const text = detail.trim() !== "" ? detail.trim() : "No error message was returned.";
	const category = hardFailureCategory(text);
	const why = category ? ` (likely ${category})` : "";
	return (
		`Claude advisor failed and is unusable${why}: ${text} The write gate is disarmed for this ` +
		`session because retrying cannot succeed on its own. Fix the cause (sign in, restore ` +
		`quota or credits, choose an available model), or set harness/${GUARDRAIL_NAME}/config.json ` +
		`to {"enabled": false} to silence this guardrail.`
	);
}

// --- pi glue -------------------------------------------------------------------

/**
 * Plain TypeBox-shaped parameter schema (a plain object is deliberate: it
 * validates identically under pi's TypeBox pipeline — verified against
 * pi-ai's validateToolArguments — and keeps the module loadable and
 * testable under plain Node, which cannot resolve the `typebox` package).
 */
const CONSULT_PARAMETER_SCHEMA = {
	type: "object",
	properties: {
		task: { type: "string", description: "What the agent is working on, in one or two sentences" },
		stage: {
			type: "string",
			enum: [...VALID_STAGES],
			description: "Why the advisor is being consulted",
		},
		approach: { type: "string", description: "The approach taken or planned so far" },
		evidence: { type: "string", description: "Relevant evidence: outputs, errors, file paths" },
		question: { type: "string", description: "The specific question for the advisor" },
	},
	required: ["task", "stage", "approach", "evidence", "question"],
};

export default function (pi: ExtensionAPI) {
	// Session-scoped in-memory state: pi extensions are in-process, so no
	// marker files exist to manage.
	const gate = createGate();

	const projectRootOf = (ctx: unknown): string => {
		const cwd = (ctx as { cwd?: unknown } | undefined)?.cwd;
		return typeof cwd === "string" && cwd !== "" ? cwd : process.cwd();
	};

	pi.registerTool({
		name: "consult_claude_advisor",
		label: "Consult Claude Advisor",
		description:
			"Read-only Claude Opus advisor: returns a plan, course correction, or completion " +
			"verdict, pairing every concern with a forward path.",
		promptSnippet:
			"Consult the Claude advisor before the first write, when stuck, before a pivot, and before declaring completion.",
		promptGuidelines: [
			"Call consult_claude_advisor with task, stage, approach, evidence, and question; stage is one of planning, stuck, pivot-check, completion-review.",
			"Every concern it raises carries a forward path: take the cheapest fix it names and verify it.",
		],
		parameters: CONSULT_PARAMETER_SCHEMA,
		async execute(
			_toolCallId: string,
			params: unknown,
			signal: AbortSignal | undefined,
			_onUpdate: unknown,
			ctx: unknown,
		) {
			const projectRoot = projectRootOf(ctx);
			const config = loadHarnessConfig(
				projectRoot,
				GUARDRAIL_NAME,
			) as ClaudeAdvisorConfig | null;
			if (!isEnabled(config)) {
				throw new Error(
					`claude-as-advisor-guardrail is disabled for this project ` +
						`(harness/${GUARDRAIL_NAME}/config.json "enabled": false). Nothing to consult.`,
				);
			}

			// Tool execute errors are THROWN on purpose: pi reports them to the
			// model with isError:true and continues. Never swallow an advisor
			// failure silently.
			const validation = validateConsult(params);
			if (validation.values === null || validation.error !== null) {
				throw new Error(validation.error ?? "invalid consult arguments");
			}

			const cli = resolveCli("claude");
			if (!cli.found) {
				applyConsultOutcome(gate, { kind: "unreachable" });
				throw new Error(unreachableAdvisorMessage(cli.note ?? "claude CLI not found"));
			}

			const result = await runExternal([...cli.argvPrefix, ...CLAUDE_ADVISOR_FLAGS], buildPrompt(validation.values), {
				timeoutSeconds: configTimeoutSeconds(config),
				signal: signal ?? null,
				cwd: projectRoot,
			});
			if (result.status === "timedout") {
				applyConsultOutcome(gate, { kind: "timedout" });
				throw new Error(timeoutAdvisorMessage(result.note ?? ""));
			}
			if (result.status !== "ok") {
				// Classify the failure (shared/advisor-failure.ts, ported from the
				// Cursor host): a HARD failure means the advisor is unusable —
				// authentication, quota/credits, model availability — and must
				// disarm the gate rather than wedge the session; a SOFT failure
				// keeps it armed. Either way the failure is THROWN, never
				// swallowed: pi reports it to the model with isError:true.
				const detail = [result.stderr, result.stdout]
					.map((stream) => stream.trim())
					.filter((stream) => stream !== "")
					.join(" ") || (result.note ?? "");
				if (classifyAdvisorFailure(detail) === "hard") {
					applyConsultOutcome(gate, { kind: "hard_failed" });
					throw new Error(hardFailureMessage(detail));
				}
				applyConsultOutcome(gate, { kind: "failed" });
				throw new Error(failedAdvisorMessage(result.stderr, result.note));
			}

			// CAP the reply before it reaches the 131k-context model.
			const reply = capToBudget(result.stdout.trim(), configReplyBudgetChars(config));
			if (reply.trim() === "") {
				// Not a success: the gate stays armed.
				throw new Error("Claude advisor returned no advice. The write gate stays armed.");
			}
			applyConsultOutcome(gate, { kind: "succeeded" });
			return { content: [{ type: "text", text: reply }] };
		},
	});

	pi.on("tool_call", (event, ctx) => {
		// Fail open: pi's tool_call fails CLOSED, so an internal guardrail
		// error must be swallowed to keep write and edit usable.
		try {
			if (event.toolName !== "write" && event.toolName !== "edit") {
				return undefined; // write/edit only — never user_bash, which is the human
			}
			const projectRoot = projectRootOf(ctx);
			const config = loadHarnessConfig(
				projectRoot,
				GUARDRAIL_NAME,
			) as ClaudeAdvisorConfig | null;
			if (!isEnabled(config)) {
				return undefined; // guardrail disabled for this project
			}
			if (gateAllowsWrite(gate)) {
				return undefined; // consulted (or disarmed): the gate is open
			}
			// Pi's write and edit input field is `path` — NOT the `file_path`
			// used by Claude Code and Cursor hook payloads. A gate ported by
			// eye reads undefined and silently passes everything, which looks
			// identical to a working gate.
			const input = (event.input ?? {}) as { path?: unknown };
			const target =
				typeof input.path === "string" && input.path.trim() !== "" ? input.path.trim() : null;
			// Block, but do NOT terminate: consulting the advisor is the
			// reachable remedy, and the local model should retry — correctly.
			return { block: true, reason: denyReason(target) };
		} catch {
			return undefined; // internal error: fail open
		}
	});
}
