// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Advisor failure classification shared by all three pi advisor guardrails.
 *
 * A consult that RUNS and exits non-zero must not wedge the session. The
 * Cursor host already solved this for Codex and Cursor advisors
 * (`plugins/cursor/codex-as-advisor-guardrail/lib/advisor_consult.py:
 * classify_failure` and `HARD_FAILURE_HINTS`, and the sibling Cursor advisor
 * server). This module ports that classification so the three pi advisors
 * share it:
 *
 *  - HARD failure — the advisor is unusable right now: not logged in,
 *    authentication, unauthorized, quota/credits/usage-limit/rate-limit/
 *    billing, or the model not available/not found/unsupported. Retrying
 *    without an operator action will fail the same way, so the gate
 *    DISARMS: an unusable advisor must not deny every write for the session.
 *  - SOFT failure — anything else (transient network blip, malformed reply,
 *    one-off error). The gate stays ARMED and the failure is reported to the
 *    model, which can fix the cause and retry.
 *
 * Either way the failure is REPORTED (thrown as a tool error with `isError:
 * true`), never swallowed. The hint list is the Cursor host's
 * `HARD_FAILURE_HINTS` verbatim; note it is deliberately broad — a message
 * that merely mentions "model" counts as model-unavailability, matching the
 * host it was ported from.
 */

/** Failure kinds a consult can be classified into. */
export type AdvisorFailureKind = "hard" | "soft";

/**
 * Lowercase substrings that mark a HARD (unusable-advisor) failure. Ported
 * verbatim from `advisor_consult.py:HARD_FAILURE_HINTS`.
 */
export const HARD_FAILURE_HINTS: readonly string[] = [
	"not logged in",
	"authentication",
	"unauthorized",
	"sign in",
	"login required",
	"quota",
	"credit",
	"usage limit",
	"rate limit",
	"billing",
	"model",
	"not available",
	"not found",
	"unsupported",
];

/** Ordered cause categories (first match wins) for human-readable messages. */
const FAILURE_CATEGORIES: readonly { label: string; terms: readonly string[] }[] = [
	{
		label: "authentication",
		terms: ["not logged in", "authentication", "unauthorized", "sign in", "login required"],
	},
	{
		label: "quota or credits",
		terms: ["quota", "credit", "usage limit", "rate limit", "billing"],
	},
	{
		label: "model availability",
		terms: ["model", "not available", "not found", "unsupported"],
	},
];

/**
 * The cause label for a HARD failure (`authentication`, `quota or credits`,
 * or `model availability`), or `null` when the detail is a SOFT failure.
 */
export function hardFailureCategory(detail: string): string | null {
	const lowered = (detail ?? "").toLowerCase();
	if (lowered === "") {
		return null;
	}
	for (const category of FAILURE_CATEGORIES) {
		if (category.terms.some((term) => lowered.includes(term))) {
			return category.label;
		}
	}
	return null;
}

/**
 * Classify a failed consult's error detail.
 *
 * HARD: the advisor is unusable (authentication, quota/credits, model
 * availability) — the gate should disarm rather than wedge the session.
 * SOFT: anything else — the gate stays armed so a transient failure cannot
 * silently open the gate, and the model sees the failure and can retry.
 *
 * Empty detail is SOFT: with no evidence of an unusable advisor, do not
 * disarm.
 */
export function classifyAdvisorFailure(detail: string): AdvisorFailureKind {
	return hardFailureCategory(detail) !== null ? "hard" : "soft";
}
