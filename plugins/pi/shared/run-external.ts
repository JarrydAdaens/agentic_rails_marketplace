// Copyright 2026 Jarryd Adaens
// Licensed under the Apache License, Version 2.0.

/**
 * External-CLI subprocess runner for pi guardrails.
 *
 * Spawns a resolved CLI (see cli-resolution.ts) with the prompt on UTF-8
 * stdin, under an explicit timeout and an optional AbortSignal so the
 * operator's Esc cancels nested work. The local model runs against a hard
 * 131k context and an error-prone local runtime can hang a subprocess for
 * minutes, so:
 *
 *  - the timeout is explicit and configurable (default 600 seconds);
 *  - captured stdout/stderr are capped with budget.ts before they can reach
 *    the model or grow memory without bound;
 *  - it NEVER throws. A timeout, a spawn failure, or a missing CLI is a
 *    returned structured failure — the caller decides how to report it.
 */

import { spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";

import { capToBudget } from "./budget.ts";

export interface ExternalRunOptions {
	/** Timeout in seconds. Default {@link DEFAULT_TIMEOUT_SECONDS} (600). */
	timeoutSeconds?: number;
	/** Abort signal (callers pass `ctx.signal`); Esc cancels the call. */
	signal?: AbortSignal | null;
	/** Working directory for the child process. */
	cwd?: string;
	/**
	 * Character budget for the captured stdout and stderr (via
	 * {@link capToBudget}). Default 16,384 per stream.
	 */
	outputBudgetChars?: number;
}

export type ExternalRunStatus = "ok" | "failed" | "timedout";

export interface ExternalRunResult {
	status: ExternalRunStatus;
	exitCode: number | null;
	stdout: string;
	stderr: string;
	/** Human-readable detail for failures, timeouts, and aborts. */
	note?: string;
}

/** Default cap on how long an external CLI may run: 600 seconds. */
export const DEFAULT_TIMEOUT_SECONDS = 600;

const DEFAULT_OUTPUT_BUDGET_CHARS = 16_384;

function positiveInt(value: unknown, fallback: number): number {
	if (typeof value === "number" && Number.isFinite(value) && value > 0) {
		return Math.floor(value);
	}
	return fallback;
}

/**
 * Run `argv` (a resolved CLI prefix plus its flags) with `prompt` written to
 * UTF-8 stdin. Resolves — never rejects — with an
 * {@link ExternalRunResult} of `ok`, `failed`, or `timedout`.
 */
export function runExternal(
	argv: string[],
	prompt: string,
	options: ExternalRunOptions = {},
): Promise<ExternalRunResult> {
	return new Promise((resolve) => {
		try {
			const command = argv[0];
			if (typeof command !== "string" || command === "") {
				resolve({
					status: "failed",
					exitCode: null,
					stdout: "",
					stderr: "",
					note: "runExternal: the argv prefix was empty.",
				});
				return;
			}

			const timeoutSeconds = positiveInt(options.timeoutSeconds, DEFAULT_TIMEOUT_SECONDS);
			const budget = positiveInt(options.outputBudgetChars, DEFAULT_OUTPUT_BUDGET_CHARS);
			const keep = budget * 2; // bound captured memory; capToBudget finishes it

			let child: ChildProcess;
			try {
				child = spawn(command, argv.slice(1), {
					cwd: typeof options.cwd === "string" && options.cwd !== "" ? options.cwd : undefined,
					windowsHide: true,
				});
			} catch (err) {
				resolve({
					status: "failed",
					exitCode: null,
					stdout: "",
					stderr: "",
					note: `Could not start the external CLI: ${err instanceof Error ? err.message : String(err)}`,
				});
				return;
			}

			let settled = false;
			let timedOut = false;
			let aborted = false;
			let stdoutText = "";
			let stderrText = "";

			const finish = (result: ExternalRunResult): void => {
				if (settled) {
					return;
				}
				settled = true;
				clearTimeout(timer);
				if (options.signal) {
					options.signal.removeEventListener("abort", onAbort);
				}
				resolve(result);
			};

			const appendOut = (chunk: Buffer): void => {
				stdoutText = stdoutText.length >= keep ? stdoutText : (stdoutText + chunk.toString("utf8")).slice(0, keep);
			};
			const appendErr = (chunk: Buffer): void => {
				stderrText = stderrText.length >= keep ? stderrText : (stderrText + chunk.toString("utf8")).slice(0, keep);
			};

			const timer = setTimeout(() => {
				timedOut = true;
				try {
					child.kill();
				} catch {
					// the child may already be gone; close will still settle
				}
			}, timeoutSeconds * 1000);

			const onAbort = (): void => {
				aborted = true;
				try {
					child.kill();
				} catch {
					// same as above
				}
			};
			if (options.signal) {
				if (options.signal.aborted) {
					onAbort();
				} else {
					options.signal.addEventListener("abort", onAbort, { once: true });
				}
			}

			child.stdout?.on("data", appendOut);
			child.stderr?.on("data", appendErr);
			// The CLI may exit before reading stdin (auth errors, bad flags):
			// an EPIPE on stdin must not become an uncaught exception.
			child.stdin?.on("error", () => {});
			child.on("error", (err: Error) => {
				finish({
					status: "failed",
					exitCode: null,
					stdout: capToBudget(stdoutText, budget),
					stderr: capToBudget(stderrText, budget),
					note: `Could not start the external CLI: ${err.message}`,
				});
			});
			child.on("close", (code: number | null) => {
				const status: ExternalRunStatus = timedOut ? "timedout" : code === 0 ? "ok" : "failed";
				const note = timedOut
					? `The external CLI timed out after ${timeoutSeconds}s.`
					: aborted
						? "The external CLI was aborted."
						: undefined;
				finish({
					status,
					exitCode: code,
					stdout: capToBudget(stdoutText, budget),
					stderr: capToBudget(stderrText, budget),
					note,
				});
			});

			child.stdin?.write(prompt, "utf8");
			child.stdin?.end();
		} catch (err) {
			// Belt and braces: the public contract is "never throws".
			resolve({
				status: "failed",
				exitCode: null,
				stdout: "",
				stderr: "",
				note: `runExternal internal error: ${err instanceof Error ? err.message : String(err)}`,
			});
		}
	});
}
