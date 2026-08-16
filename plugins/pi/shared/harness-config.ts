// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Harness-config loading for pi guardrails.
 *
 * Every guardrail reads its optional per-project config from
 * `harness/<guardrail-name>/config.json` in the project root — the same seam
 * the Claude, Codex, and Cursor hosts use, so a project never grows a second
 * config location for one guardrail.
 *
 * The convention is identical across hosts and guardrails:
 *  - absent, empty, or malformed config means "enforce with defaults";
 *  - `"enabled": false` stands the guardrail down for that project only.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

export interface HarnessConfig {
	enabled?: boolean;
	[key: string]: unknown;
}

/**
 * Load `harness/<guardrail>/config.json` from a project root.
 *
 * Absent file, empty file, malformed JSON, and a non-object payload all
 * return `null`, which callers treat as "no project config: enforce with
 * defaults". This function never throws.
 */
export function loadHarnessConfig(
	projectRoot: string,
	guardrail: string,
): HarnessConfig | null {
	try {
		const raw = readFileSync(join(projectRoot, "harness", guardrail, "config.json"), "utf8");
		if (!raw.trim()) {
			return null; // empty config: treat as absent, enforce with defaults
		}
		const parsed: unknown = JSON.parse(raw);
		if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
			return null; // malformed config: treat as absent, enforce with defaults
		}
		return parsed as HarnessConfig;
	} catch {
		return null; // missing file or malformed config: enforce with defaults
	}
}

/**
 * A guardrail is enabled by default; only an explicit `"enabled": false` in
 * the project config stands it down.
 */
export function isEnabled(config: HarnessConfig | null): boolean {
	return config?.enabled !== false;
}
