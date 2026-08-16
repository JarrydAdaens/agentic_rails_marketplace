// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * readme-name-guardrail (pi host)
 *
 * A `readme.md` (any capitalization) anywhere but the project root piles up
 * and crowds terminal file references, so the codebase keeps a single,
 * unambiguous README and every other one carries a descriptive prefix. This
 * guardrail enforces that rule with two `tool_call` enforcement points:
 *
 *   - `write` / `edit`: the target path must not be a forbidden readme;
 *   - `bash`: `git add` and `git commit` must not stage or commit one — the
 *     backstop for readmes created outside the agent or before install.
 *
 * This is a port of the decision logic in
 * plugins/cursor/readme-name-guardrail/hooks/readme-guard-common.ps1 and its
 * two callers block-readme-write.ps1 and block-readme-git.ps1. The stdin
 * reading, BOM stripping, and JSON response envelope of the PowerShell hooks
 * are deliberately NOT ported: pi hooks are in-process and need none of that
 * transport.
 *
 * It blocks with `{ block: true, reason }` and does NOT terminate, because a
 * legitimate remedy exists — rename the file with a descriptive prefix, and
 * the deny message names the suggested name.
 *
 * Fail open: every handler body is wrapped so an internal guardrail error
 * allows the guarded tool through rather than blocking it. Pi's `tool_call`
 * fails CLOSED (an unhandled throw wedges the guarded tool for the session),
 * so this wrapping is mandatory, not stylistic.
 */

import { spawnSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import { basename, splitSegments, WRAPPERS } from "../../shared/bash-segments.ts";
import { isEnabled, loadHarnessConfig } from "../../shared/harness-config.ts";

export const GUARDRAIL_NAME = "readme-name-guardrail";

/** Config shape: `harness/readme-name-guardrail/config.json`. */
export interface ReadmeNameConfig {
	enabled?: boolean;
	allowPaths?: string[];
}

export interface ReadmeDecision {
	blocked: boolean;
	/** Offending paths as repo-relative POSIX paths, for the deny message. */
	offenders: string[];
	/** Suggested prefixed name, for the write-path deny message. */
	suggested: string | null;
}

export function notBlocked(): ReadmeDecision {
	return { blocked: false, offenders: [], suggested: null };
}

/** Paths compare case-insensitively on Windows, byte-exactly elsewhere. */
const CASE_INSENSITIVE = process.platform === "win32";

function stripTrailingSeparator(p: string): string {
	return p.replace(/[\\/]+$/u, "");
}

function samePath(a: string, b: string): boolean {
	const x = stripTrailingSeparator(resolve(a));
	const y = stripTrailingSeparator(resolve(b));
	return CASE_INSENSITIVE ? x.toLowerCase() === y.toLowerCase() : x === y;
}

function startsWithDir(path: string, dir: string): boolean {
	const a = stripTrailingSeparator(resolve(path));
	const d = stripTrailingSeparator(resolve(dir));
	return CASE_INSENSITIVE ? a.toLowerCase().startsWith(d.toLowerCase()) : a.startsWith(d);
}

/** The leaf must be exactly `readme.md` in any casing — `api-readme.md` is fine. */
export function isReadmeLeaf(name: string): boolean {
	return name.toLowerCase() === "readme.md";
}

/**
 * A path is forbidden when its filename is exactly `readme.md` (any casing)
 * and its parent directory is NOT the project root — the root's single README
 * is the one allowed.
 */
export function isForbiddenReadme(absPath: string, root: string): boolean {
	if (!absPath) {
		return false;
	}
	const full = resolve(absPath);
	if (!isReadmeLeaf(full.split(/[\\/]/u).pop() ?? "")) {
		return false;
	}
	return !samePath(dirname(full), root);
}

/**
 * A repo-relative POSIX path, for `allowPaths` matching and deny messages:
 * strip the project root when the path is inside it, then convert separators.
 */
export function relativePosixPath(absPath: string, root: string): string {
	const toPosix = (p: string) => p.replace(/\\/gu, "/");
	const rootPosix = toPosix(resolve(root)).replace(/\/+$/u, "");
	const fullPosix = toPosix(resolve(absPath));
	const matches = CASE_INSENSITIVE
		? fullPosix.toLowerCase().startsWith(rootPosix.toLowerCase() + "/")
		: fullPosix.startsWith(rootPosix + "/");
	// Inside the root: the relative tail. Outside: the path as-is (still posix).
	return matches
		? fullPosix.slice(rootPosix.length).replace(/^\//u, "")
		: fullPosix.replace(/^\/+\//u, "");
}

/**
 * `allowPaths`: regexes matched (case-insensitively) against the
 * repo-relative POSIX path; any match is a narrow, project-declared
 * exception. An invalid regex is skipped, never fatal.
 */
export function isAllowedByConfig(relPosixPath: string, config: ReadmeNameConfig | null): boolean {
	const allowPaths = config?.allowPaths;
	if (!Array.isArray(allowPaths)) {
		return false;
	}
	for (const pattern of allowPaths) {
		if (typeof pattern !== "string" || pattern.trim() === "") {
			continue;
		}
		try {
			if (new RegExp(pattern, "i").test(relPosixPath)) {
				return true;
			}
		} catch {
			// malformed regex in project config: skip it, keep enforcing
		}
	}
	return false;
}

/**
 * Suggest a descriptive prefix drawn from the containing folder, matching the
 * `creatures-readme.md` shape the deny message asks the agent to adopt.
 */
export function suggestedReadmeName(absPath: string): string {
	const parentLeaf = basename(dirname(resolve(absPath)));
	const slug = parentLeaf.toLowerCase().replace(/[^a-z0-9]+/gu, "-").replace(/^-+|-+$/gu, "");
	return slug ? `${slug}-readme.md` : "topic-readme.md";
}

// --- the write / edit enforcement point -------------------------------------

/**
 * The deny decision for one `write`/`edit` target path.
 *
 * Absent/empty/malformed config means "enforce with defaults";
 * `"enabled": false` stands the guardrail down; `allowPaths` is a per-project
 * allowlist of regexes against the repo-relative POSIX path.
 */
export function decideWrite(
	filePath: string,
	root: string,
	config: ReadmeNameConfig | null = null,
): ReadmeDecision {
	if (!isEnabled(config)) {
		return notBlocked();
	}
	if (typeof filePath !== "string" || filePath.trim() === "") {
		return notBlocked();
	}
	const abs = resolve(root, filePath);
	if (!isForbiddenReadme(abs, root)) {
		return notBlocked();
	}
	const rel = relativePosixPath(abs, root);
	if (isAllowedByConfig(rel, config)) {
		return notBlocked();
	}
	return { blocked: true, offenders: [rel], suggested: suggestedReadmeName(abs) };
}

// --- the git enforcement point ----------------------------------------------

/** One parsed `git <subcommand> [args]` invocation, honoring `-C <dir>`. */
interface GitInvocation {
	repoDir: string | null;
	sub: string;
	args: string[];
}

/**
 * Parse one segment into a git invocation, or `null` when it is not one.
 * Skips inline `VAR=value` assignments and wrapper commands; honors the
 * `-C <dir>` global option and skips other global options.
 */
export function getGitInvocation(segment: string): GitInvocation | null {
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
		return null;
	}
	// The subcommand and its arguments begin after the git token.
	let j = i + 1;
	let repoDir: string | null = null;
	while (j < tokens.length) {
		const token = tokens[j];
		if (token === "-C") {
			repoDir = tokens[j + 1] ?? null;
			j += 2;
			continue;
		}
		if (token === "-c") {
			j += 2; // -c key=value
			continue;
		}
		if (token.startsWith("-")) {
			j++; // other global option
			continue;
		}
		break;
	}
	if (j >= tokens.length) {
		return null;
	}
	const sub = tokens[j];
	return { repoDir, sub, args: tokens.slice(j + 1) };
}

function isDirectory(p: string): boolean {
	try {
		return existsSync(p) && statSync(p).isDirectory();
	} catch {
		return false;
	}
}

/** Run a read-only git query in the repository directory; `[]` on any failure. */
function runGit(repoDir: string, args: string[]): string[] {
	try {
		const result = spawnSync("git", ["-C", repoDir, ...args], {
			encoding: "utf8",
			timeout: 10_000,
		});
		if (result.status !== 0 || typeof result.stdout !== "string") {
			return [];
		}
		return result.stdout
			.split(/\r?\n/u)
			.map((line) => line.trim())
			.filter((line) => line !== "");
	} catch {
		return [];
	}
}

interface PorcelainEntry {
	status: string;
	path: string;
}

/** Parse `git status --porcelain` lines into status/path entries (renames take the new path). */
function porcelainEntries(lines: string[]): PorcelainEntry[] {
	const entries: PorcelainEntry[] = [];
	for (const line of lines) {
		if (line.trim() === "") {
			continue;
		}
		const status = line.slice(0, Math.min(2, line.length));
		let rest = line.length > 3 ? line.slice(3) : "";
		if (rest.includes("->")) {
			rest = rest.split("->").pop() ?? "";
		}
		rest = rest.trim().replace(/^"|"$/gu, "");
		if (rest !== "") {
			entries.push({ status, path: rest });
		}
	}
	return entries;
}

/** Offenders a `git add` would stage: explicit pathspecs plus bulk/dir expansion. */
function addOffenders(invocation: GitInvocation, repoDir: string): string[] {
	const offenders = new Set<string>();
	let bulkAll = false;
	let updateOnly = false;
	const dirSpecs: string[] = [];

	for (const arg of invocation.args) {
		const raw = arg.replace(/^"|"$/gu, "");
		if (raw === "-A" || raw === "--all") {
			bulkAll = true;
			continue;
		}
		if (raw === "-u" || raw === "--update") {
			updateOnly = true;
			continue;
		}
		if (raw === "." || raw === "./") {
			bulkAll = true;
			continue;
		}
		if (raw === "--") {
			continue;
		}
		if (raw.startsWith("-")) {
			continue; // any other flag
		}
		const abs = resolve(repoDir, raw);
		if (isDirectory(abs)) {
			dirSpecs.push(stripTrailingSeparator(abs));
		} else if (isForbiddenReadme(abs, repoDir)) {
			offenders.add(relativePosixPath(abs, repoDir));
		}
	}

	if (bulkAll || updateOnly || dirSpecs.length > 0) {
		for (const entry of porcelainEntries(
			runGit(repoDir, ["status", "--porcelain", "--untracked-files=all"]),
		)) {
			if (updateOnly && !bulkAll && entry.status === "??") {
				continue; // -u ignores untracked files
			}
			const abs = resolve(repoDir, entry.path);
			if (!isForbiddenReadme(abs, repoDir)) {
				continue;
			}
			if (dirSpecs.length > 0 && !bulkAll && !updateOnly) {
				if (!dirSpecs.some((dir) => startsWithDir(abs, dir))) {
					continue;
				}
			}
			offenders.add(relativePosixPath(abs, repoDir));
		}
	}
	return [...offenders];
}

/**
 * Offenders a `git commit` would commit: already-staged paths, tracked
 * modifications when `-a` is present, and the explicit path arguments —
 * `git commit docs/readme.md` names the offender directly.
 */
function commitOffenders(invocation: GitInvocation, repoDir: string): string[] {
	let all = false;
	for (const arg of invocation.args) {
		if (arg === "--all") {
			all = true;
			continue;
		}
		// short-flag bundle containing 'a' (-a, -am, ...): in `git commit`, 'a' means --all
		if (/^-[a-zA-Z]+$/u.test(arg) && arg.includes("a")) {
			all = true;
		}
	}

	const candidates = new Set<string>();
	for (const p of runGit(repoDir, ["diff", "--cached", "--name-only"])) {
		candidates.add(p);
	}
	if (all) {
		for (const p of runGit(repoDir, ["ls-files", "-m"])) {
			candidates.add(p);
		}
	}
	for (const arg of invocation.args) {
		const raw = arg.replace(/^"|"$/gu, "");
		if (raw === "--" || raw === "." || raw === "./" || raw.startsWith("-")) {
			continue;
		}
		candidates.add(raw);
	}

	const offenders = new Set<string>();
	for (const candidate of candidates) {
		const abs = resolve(repoDir, candidate);
		if (isForbiddenReadme(abs, repoDir)) {
			offenders.add(relativePosixPath(abs, repoDir));
		}
	}
	return [...offenders];
}

/**
 * The deny decision for one bash command: does a `git add` / `git commit`
 * anywhere in the chain stage or commit a forbidden readme?
 */
export function decideGit(
	command: string,
	root: string,
	config: ReadmeNameConfig | null = null,
): ReadmeDecision {
	if (!isEnabled(config)) {
		return notBlocked();
	}
	if (typeof command !== "string" || command.trim() === "") {
		return notBlocked();
	}
	if (!/\bgit\b/iu.test(command)) {
		return notBlocked(); // fast bail: no git, nothing to inspect
	}

	const offenders = new Set<string>();
	for (const segment of splitSegments(command)) {
		const invocation = getGitInvocation(segment);
		if (invocation === null) {
			continue;
		}
		const repoDir = invocation.repoDir !== null ? resolve(root, invocation.repoDir) : root;
		if (invocation.sub === "add") {
			for (const offender of addOffenders(invocation, repoDir)) {
				offenders.add(offender);
			}
		} else if (invocation.sub === "commit") {
			for (const offender of commitOffenders(invocation, repoDir)) {
				offenders.add(offender);
			}
		}
	}

	const filtered = [...offenders].filter((offender) => !isAllowedByConfig(offender, config));
	if (filtered.length === 0) {
		return notBlocked();
	}
	return { blocked: true, offenders: filtered, suggested: null };
}

// --- deny messages (ported verbatim from the Cursor-host hooks) --------------

/** The write-path deny text. The model acts on it; the suggestion is per-path. */
export function denyWriteReason(relPosixPath: string, suggested: string): string {
	return (
		`readme-name-guardrail: creating '${relPosixPath}' is forbidden. The name 'readme.md' ` +
		`(any capitalization) is reserved for the single project-root README; extra files ` +
		`with that exact name pile up and crowd terminal file references. Give it a ` +
		`descriptive prefix instead - e.g. '${suggested}' - then retry. A prefixed name like ` +
		`that is allowed anywhere.`
	);
}

/** The git-path deny text. */
export function denyGitReason(offenders: string[]): string {
	const list = offenders.map((offender) => `'${offender}'`).join(", ");
	return (
		`readme-name-guardrail: this git command would stage or commit forbidden README ` +
		`file(s): ${list}. The name 'readme.md' (any capitalization) is reserved for the single ` +
		`project-root README; extra files with that exact name crowd terminal file references. ` +
		`Rename each with a descriptive prefix - e.g. 'creatures-readme.md' - and 'git restore ` +
		`--staged <path>' any that are already staged, then retry.`
	);
}

// --- pi glue ------------------------------------------------------------------

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", (event, ctx) => {
		// Fail open: pi's tool_call fails CLOSED, so an internal guardrail error
		// must be swallowed to keep the guarded tool usable. A guardrail bug
		// must never wedge write, edit, or bash.
		try {
			const projectRoot =
				typeof ctx?.cwd === "string" && ctx.cwd !== "" ? ctx.cwd : process.cwd();
			const config = loadHarnessConfig(
				projectRoot,
				GUARDRAIL_NAME,
			) as ReadmeNameConfig | null;

			if (event.toolName === "write" || event.toolName === "edit") {
				const filePath = (event.input as { path?: unknown } | undefined)?.path;
				if (typeof filePath !== "string" || filePath.trim() === "") {
					return undefined; // nothing to inspect
				}
				const decision = decideWrite(filePath, projectRoot, config);
				if (!decision.blocked) {
					return undefined;
				}
				// Block, but do NOT terminate: renaming is the legitimate remedy.
				return {
					block: true,
					reason: denyWriteReason(
						decision.offenders[0],
						decision.suggested ?? "topic-readme.md",
					),
				};
			}

			if (event.toolName !== "bash") {
				return undefined;
			}
			const command = (event.input as { command?: unknown } | undefined)?.command;
			if (typeof command !== "string" || command.trim() === "") {
				return undefined; // nothing to inspect
			}
			const decision = decideGit(command, projectRoot, config);
			if (!decision.blocked) {
				return undefined;
			}
			// Block, but do NOT terminate: the rename remedy is reachable.
			return { block: true, reason: denyGitReason(decision.offenders) };
		} catch {
			return undefined; // internal error: fail open
		}
	});
}
