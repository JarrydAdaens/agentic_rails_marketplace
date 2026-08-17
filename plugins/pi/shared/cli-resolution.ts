// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * Windows CLI resolution for pi guardrails.
 *
 * The advisor guardrails spawn external CLIs — `claude`, `codex`, and
 * Cursor's `agent` — without requiring operator PATH changes. This module
 * ports the search-path knowledge from
 * plugins/cursor/codex-as-advisor-guardrail/lib/windows_runtime.py (the
 * known per-vendor install locations and the `.cmd`/`.bat` shim handling)
 * into an independent, side-effect-free TypeScript reimplementation.
 *
 * Two rules it encodes:
 *  - a `.cmd` or `.bat` shim MUST be invoked through `cmd.exe /d /c` when
 *    spawned without a shell — spawning the shim directly from Node fails;
 *  - resolution NEVER throws. A missing CLI is a returned "not found"
 *    result so the guardrail can report itself offline and disarm, not
 *    wedge the session.
 *
 * The environment is injectable (defaults to `process.env`) so the search
 * paths are testable in isolation, the same way the Cursor-host module takes
 * an injectable registry reader.
 */

import { existsSync, statSync } from "node:fs";
import { join } from "node:path";

export interface ResolvedCli {
	/** True when an executable (or spawnable shim) was located. */
	found: boolean;
	/** Absolute path of the executable or shim that was found. */
	path?: string;
	/**
	 * Spawn-ready argv prefix: `[executable]`, or
	 * `[cmd.exe, "/d", "/c", shim]` for a `.cmd`/`.bat` shim. Callers append
	 * the CLI's own flags after this prefix.
	 */
	argvPrefix?: string[];
	/** Human-readable reason when not found, or a resolution note. */
	note?: string;
}

/** Injectable environment (defaults to `process.env`). */
export type CliEnvironment = Record<string, string | undefined>;

const IS_WINDOWS = process.platform === "win32";

/** File test that never throws. */
export function isFile(path: string): boolean {
	try {
		return existsSync(path) && statSync(path).isFile();
	} catch {
		return false;
	}
}

/** True for `.cmd` / `.bat` shims (any casing) that need `cmd.exe /d /c`. */
export function isBatchShim(path: string): boolean {
	return /\.(cmd|bat)$/iu.test(path);
}

/**
 * The known per-vendor install locations, ported from
 * `windows_runtime.py:_known_candidates`. Order matters: the first existing
 * file wins. Names other than `claude`, `codex`, and `agent` have no known
 * locations and rely on the PATH search.
 */
export function knownCandidates(name: string, env: CliEnvironment): string[] {
	const local = env.LOCALAPPDATA;
	const roaming = env.APPDATA;
	const profile = env.USERPROFILE;
	const values: string[] = [];

	if (name === "agent") {
		if (local) {
			values.push(join(local, "cursor-agent", "agent.cmd"));
			values.push(join(local, "cursor-agent", "agent.exe"));
		}
	} else if (name === "codex") {
		if (local) {
			values.push(join(local, "Programs", "OpenAI", "Codex", "bin", "codex.exe"));
			values.push(join(local, "OpenAI", "Codex", "bin", "codex.exe"));
		}
		if (roaming) {
			values.push(join(roaming, "npm", "codex.cmd"));
		}
	} else if (name === "claude") {
		if (local) {
			values.push(join(local, "pnpm", "claude.cmd"));
		}
		if (roaming) {
			values.push(join(roaming, "npm", "claude.cmd"));
		}
		if (profile) {
			values.push(join(profile, ".local", "bin", "claude.exe"));
			values.push(join(profile, ".claude", "local", "claude.exe"));
		}
	}
	return values;
}

/**
 * Search `PATH` for the CLI. On Windows a directory match counts as `name`
 * with `.exe`, `.cmd`, or `.bat` (in that order); elsewhere the bare name.
 */
export function searchPath(name: string, env: CliEnvironment): string | null {
	const pathValue = env.PATH ?? env.Path;
	if (!pathValue) {
		return null;
	}
	const separator = IS_WINDOWS ? ";" : ":";
	const suffixes = IS_WINDOWS ? [`${name}.exe`, `${name}.cmd`, `${name}.bat`] : [name];
	for (const entry of pathValue.split(separator)) {
		const dir = entry.trim().replace(/^"(.*)"$/u, "$1");
		if (dir === "") {
			continue;
		}
		for (const suffix of suffixes) {
			const candidate = join(dir, suffix);
			if (isFile(candidate)) {
				return candidate;
			}
		}
	}
	return null;
}

/**
 * Locate an external CLI by name (`claude`, `codex`, `agent`).
 *
 * Returns a spawn-ready argv prefix, or `{ found: false, note }` — it never
 * throws. A `.cmd`/`.bat` shim is wrapped in `cmd.exe /d /c` so it can be
 * spawned without a shell; if `cmd.exe` itself cannot be located the result
 * is "not found" rather than a spawn that will fail.
 */
export function resolveCli(name: string, env: CliEnvironment = process.env): ResolvedCli {
	try {
		let executable: string | null = null;
		for (const candidate of knownCandidates(name, env)) {
			if (isFile(candidate)) {
				executable = candidate;
				break;
			}
		}
		if (executable === null) {
			executable = searchPath(name, env);
		}
		if (executable === null) {
			return {
				found: false,
				note: `${name} was not found in the usual install locations or on PATH. ` +
					`Install it, add it to PATH, or disable the guardrail that needs it.`,
			};
		}
		if (isBatchShim(executable)) {
			const systemRoot = env.SystemRoot || env.WINDIR || "C:\\Windows";
			const commandProcessor = join(systemRoot, "System32", "cmd.exe");
			if (!isFile(commandProcessor)) {
				return {
					found: false,
					note: `${executable} is a .cmd/.bat shim, but cmd.exe was not found at ` +
						`${commandProcessor}, so it cannot be spawned without a shell.`,
				};
			}
			// /d skips AUTOEXEC; /c runs the shim with the caller's flags.
			return { found: true, path: executable, argvPrefix: [commandProcessor, "/d", "/c", executable] };
		}
		return { found: true, path: executable, argvPrefix: [executable] };
	} catch (err) {
		// Resolution must never throw: an unreachable CLI is a returned failure.
		return {
			found: false,
			note: `resolving ${name} failed: ${err instanceof Error ? err.message : String(err)}`,
		};
	}
}
