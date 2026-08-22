#!/usr/bin/env python3
"""Read-only diagnostics for Cursor's local Agentic Rails marketplace state."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MARKETPLACE = "agentic-rails"
REPOSITORY = "agentic_rails_marketplace"
UPSTREAM_NOTE = "https://forum.cursor.com/t/plugin-update-version-management-how-are-installed-plugins-updated/166454/8"


def run(*args: str, cwd: Path | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    return result.returncode == 0, result.stdout.strip() or result.stderr.strip()


def cursor_home() -> Path:
    return Path(os.environ.get("CURSOR_HOME") or os.environ.get("USERPROFILE") or Path.home()) / ".cursor"


def commit_date(repo: Path, commit: str | None) -> str:
    if not commit:
        return "UNKNOWN"
    ok, value = run("git", "show", "-s", "--format=%aI", commit, cwd=repo)
    if not ok:
        return "UNKNOWN"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d %b %Y %H:%M %Z")
    except ValueError:
        return value


def manifest_version(path: Path) -> str:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "not declared"
    if manifest.get("version"):
        return str(manifest["version"])
    description = str(manifest.get("description", ""))
    return description.split(" — ", 1)[0] if description.startswith("v") else "not declared"


@dataclass
class Plugin:
    name: str
    commit: str | None
    version: str
    state: str


def marketplace_checkout(home: Path) -> Path | None:
    base = home / "plugins" / "marketplaces"
    if not base.is_dir():
        return None
    candidates = [p for p in base.rglob(REPOSITORY) if p.is_dir()]
    revisions = [child for candidate in candidates for child in candidate.iterdir() if child.is_dir() and (child / ".git").exists()]
    return max(revisions, key=lambda path: path.stat().st_mtime, default=None)


def plugins(home: Path, checkout: Path | None, expected_commit: str | None) -> list[Plugin]:
    cache = home / "plugins" / "cache" / MARKETPLACE
    catalog: set[str] = set()
    if checkout:
        try:
            catalog_data = json.loads((checkout / ".cursor-plugin" / "marketplace.json").read_text(encoding="utf-8"))
            catalog = {item["name"] for item in catalog_data.get("plugins", [])}
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    result: list[Plugin] = []
    for plugin_dir in sorted(cache.iterdir()) if cache.is_dir() else []:
        revisions = [p for p in plugin_dir.iterdir() if p.is_dir()]
        if not revisions:
            continue
        revision = max(revisions, key=lambda path: path.stat().st_mtime)
        commit = revision.name if len(revision.name) >= 7 else None
        if plugin_dir.name not in catalog:
            state = "ORPHANED"
        elif expected_commit is None or commit is None:
            state = "UNKNOWN"
        else:
            state = "CURRENT" if commit == expected_commit else "STALE"
        result.append(Plugin(plugin_dir.name, commit, manifest_version(revision / ".cursor-plugin" / "plugin.json"), state))
    for missing in sorted(catalog - {plugin.name for plugin in result}):
        result.append(Plugin(missing, None, "not installed", "MISSING"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", action="store_true")
    parser.parse_args()
    home = cursor_home()
    checkout = marketplace_checkout(home)
    print("Agentic Rails Marketplace Doctor")
    print()
    if not checkout:
        print("Marketplace\n  status: MISSING\n\nOverall\n  BROKEN")
        return 2
    ok, local = run("git", "rev-parse", "HEAD", cwd=checkout)
    local = local if ok else None
    remote_ok, remote = run("git", "remote", "get-url", "origin", cwd=checkout)
    ref_ok, ref = run("git", "symbolic-ref", "--short", "HEAD", cwd=checkout)
    remote_ok, remote_tip = run("git", "ls-remote", "origin", "HEAD", cwd=checkout)
    upstream = remote_tip.split()[0] if remote_ok and remote_tip else None
    if upstream and local == upstream:
        relation = "CURRENT"
    elif upstream and local:
        relation = "STALE" if local != upstream else "CURRENT"
    else:
        relation = "UNREACHABLE" if not remote_ok else "UNKNOWN"
    print("Marketplace")
    print(f"  path:            {checkout}")
    print(f"  remote:          {remote if remote_ok else 'UNKNOWN'}")
    print(f"  ref:             {ref if ref_ok else 'DETACHED/UNKNOWN'}")
    print(f"  local commit:    {local or 'UNKNOWN'} — {commit_date(checkout, local)}")
    print(f"  upstream commit: {upstream or 'UNKNOWN'} — {commit_date(checkout, upstream)}")
    print(f"  status:          {relation}")
    observed = plugins(home, checkout, local)
    print("\nInstalled plugins")
    print(f"  {'Plugin':35} {'Installed':14} {'Version':14} State")
    for plugin in observed:
        print(f"  {plugin.name:35} {(plugin.commit or '—')[:12]:14} {plugin.version:14} {plugin.state}")
    advisor_count = sum(bool("advisor" in plugin.name and plugin.commit) for plugin in observed)
    critic_count = sum(bool("critic" in plugin.name and plugin.commit) for plugin in observed)
    print("\nRuntime")
    for executable in ("claude", "codex"):
        path = shutil.which(executable)
        ok, _ = run(executable, "--version") if path else (False, "missing")
        print(f"  {executable.title()}: {'REACHABLE' if ok else ('FOUND BUT FAILED' if path else 'MISSING')}")
    print("\nInstallation hygiene")
    print(f"  Advisors observed: {advisor_count}")
    print(f"  Critics observed:  {critic_count}")
    if advisor_count > 1 or critic_count > 1:
        print("  WARNING: Multiple advisors or critics are supported but usually unnecessary.")
    stale = any(plugin.state in {"STALE", "ORPHANED"} for plugin in observed)
    broken = relation == "MISSING"
    overall = "BROKEN" if broken else "DEGRADED" if stale or relation in {"STALE", "UNREACHABLE"} else "HEALTHY"
    if stale:
        print("\nKnown Cursor issue")
        print("  Personal Git marketplace payloads can remain pinned after the marketplace checkout updates.")
        print(f"  {UPSTREAM_NOTE}")
        print("  Try Cursor's normal reinstall path, rerun Doctor, then consider the experimental Surgeon.")
    print(f"\nOverall\n  {overall}")
    return 0 if overall != "BROKEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
