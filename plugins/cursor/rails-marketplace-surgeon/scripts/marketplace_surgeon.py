#!/usr/bin/env python3
"""Explicit, no-backup cache repair for Cursor's Agentic Rails marketplace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

MARKETPLACE = "agentic-rails"
REPOSITORY = "agentic_rails_marketplace"


def run(*args: str, cwd: Path | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    return result.returncode == 0, result.stdout.strip() or result.stderr.strip()


def cursor_home() -> Path:
    return Path(os.environ.get("CURSOR_HOME") or os.environ.get("USERPROFILE") or Path.home()) / ".cursor"


def checkout(home: Path) -> Path | None:
    base = home / "plugins" / "marketplaces"
    candidates = [p for p in base.rglob(REPOSITORY) if p.is_dir()] if base.is_dir() else []
    revisions = [child for candidate in candidates for child in candidate.iterdir() if child.is_dir() and (child / ".git").exists()]
    return max(revisions, key=lambda path: path.stat().st_mtime, default=None)


def catalog_names(repo: Path) -> set[str]:
    try:
        data = json.loads((repo / ".cursor-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        return {entry["name"] for entry in data.get("plugins", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        return set()


def stale_payloads(home: Path, names: set[str], target: str) -> list[tuple[str, Path, str]]:
    cache = home / "plugins" / "cache" / MARKETPLACE
    result: list[tuple[str, Path, str]] = []
    for plugin_dir in sorted(cache.iterdir()) if cache.is_dir() else []:
        if plugin_dir.name not in names:
            continue
        revisions = [p for p in plugin_dir.iterdir() if p.is_dir()]
        if not revisions:
            continue
        active = max(revisions, key=lambda path: path.stat().st_mtime)
        if active.name != target:
            result.append((plugin_dir.name, active, target))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="perform the displayed cache mutation")
    args = parser.parse_args()
    home = cursor_home()
    repo = checkout(home)
    print("Agentic Rails Marketplace Surgeon")
    if not repo:
        print("UNSAFE: Agentic Rails marketplace checkout was not found; no mutation performed.")
        return 2
    remote_ok, remote_tip = run("git", "ls-remote", "origin", "HEAD", cwd=repo)
    if not remote_ok or not remote_tip:
        print("UNSAFE: upstream tip could not be resolved; no mutation performed.")
        return 2
    target = remote_tip.split()[0]
    local_ok, local = run("git", "rev-parse", "HEAD", cwd=repo)
    print(f"Marketplace\n  path:     {repo}\n  before:   {local if local_ok else 'UNKNOWN'}\n  upstream: {target}")
    names = catalog_names(repo)
    if not names:
        print("UNSAFE: Cursor marketplace manifest is unreadable; no mutation performed.")
        return 2
    stale = stale_payloads(home, names, target)
    print("\nPlanned plugin cache repair")
    if stale:
        for name, installed, _ in stale:
            print(f"  {name}: {installed.name} -> {target}")
    else:
        print("  No stale observed payloads.")
    if not args.apply:
        print("\nDRY RUN COMPLETE — no state changed. Re-run with --apply only after explicit approval.")
        return 0
    print("\nApplying")
    ok, message = run("git", "fetch", "origin", cwd=repo)
    if not ok:
        print(f"FAILED: fetch failed: {message}")
        return 2
    ok, message = run("git", "reset", "--hard", target, cwd=repo)
    if not ok:
        print(f"FAILED: checkout update failed: {message}")
        return 2
    names = catalog_names(repo)
    for name, old_payload, _ in stale:
        source = repo / "plugins" / "cursor" / name
        target_payload = home / "plugins" / "cache" / MARKETPLACE / name / target
        if not source.is_dir():
            print(f"  {name}: ORPHANED after refresh; left unchanged")
            continue
        if target_payload.exists():
            print(f"  {name}: current payload already exists")
            continue
        target_payload.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target_payload)
        print(f"  {name}: created current payload {target}")
    ok, final = run("git", "rev-parse", "HEAD", cwd=repo)
    if not ok or final != target:
        print("FAILED: marketplace checkout verification failed.")
        return 2
    print("\nSURGERY COMPLETE")
    print("Filesystem payloads were updated without backups. Cursor's account-backed pin selection is not observable here.")
    print("Run /rails-marketplace-doctor to verify the final observed state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
