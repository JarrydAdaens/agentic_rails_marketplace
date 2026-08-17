// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Deterministic output capping for pi guardrails.
 *
 * The local model runs with a hard 131,072-token context; every byte a
 * guardrail injects is a byte the operator does not get. Advisor replies and
 * review output are capped, not merely "kept short". Capping here is
 * deterministic — the same input always yields the same output — so it is
 * testable in isolation.
 */

/** Default marker appended when a string is truncated. */
export const TRUNCATION_MARKER = "…[truncated]";

/**
 * Cap `text` to at most `limit` characters.
 *
 * If the text fits, it is returned unchanged. Otherwise it is cut so that
 * the result — text plus marker — is exactly `limit` characters long. If
 * `limit` is too small to fit the marker, the text is cut to `limit`
 * characters with no marker. A non-positive limit yields an empty string.
 */
export function capToBudget(
	text: string,
	limit: number,
	marker: string = TRUNCATION_MARKER,
): string {
	if (limit <= 0) {
		return "";
	}
	if (text.length <= limit) {
		return text;
	}
	if (limit <= marker.length) {
		return text.slice(0, limit);
	}
	return text.slice(0, limit - marker.length) + marker;
}
