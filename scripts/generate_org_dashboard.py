#!/usr/bin/env python3
"""
CSTH-Projects Organization Dashboard Generator

Fetches repo metadata from the GitHub API (using an org-level PAT)
and generates a modern profile/README.md for the organization.

Exposes ONLY metadata — no source code, no secrets. Safe for public view.

Usage:
    python generate_org_dashboard.py              # writes profile/README.md
    python generate_org_dashboard.py --stdout      # prints to stdout
    GITHUB_TOKEN=ghp_xxx python generate_org_dashboard.py  # uses PAT for private repos

Required env:
    GITHUB_TOKEN  — PAT with `read:org` + `repo` (metadata) scope
    ORG_NAME      — GitHub org name (default: CSTH-Projects)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any

ORG_NAME = os.getenv("ORG_NAME", "CSTH-Projects")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
API_BASE = "https://api.github.com"
OUTPUT_DIR = "profile"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "README.md")

# ── Language color badges ────────────────────────────────────────────────
LANG_COLORS = {
    "TypeScript": "3178C6",
    "JavaScript": "F7DF1E",
    "Python": "3776AB",
    "Java": "ED8B00",
    "Go": "00ADD8",
    "Rust": "DEA584",
    "C#": "239120",
    "Shell": "89E051",
    "HTML": "E34C26",
    "CSS": "563D7C",
    "Dockerfile": "384D54",
}

LANG_EMOJIS = {
    "TypeScript": "🔷",
    "JavaScript": "🟡",
    "Python": "🐍",
    "Java": "☕",
    "Go": "🔵",
    "Rust": "🦀",
    "Shell": "🐚",
}


def api_get(path: str) -> Any:
    """Make an authenticated GET request to the GitHub API."""
    url = f"{API_BASE}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"API error {e.code} for {url}: {e.reason}", file=sys.stderr)
        if e.code == 403:
            print("Rate limited or insufficient permissions.", file=sys.stderr)
        return None


def fetch_all_repos() -> list[dict]:
    """Fetch all org repos (paginated)."""
    repos = []
    page = 1
    while True:
        data = api_get(f"/orgs/{ORG_NAME}/repos?per_page=100&page={page}&sort=pushed&direction=desc")
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


def fetch_repo_commits_count(owner: str, repo: str) -> int:
    """Get total commit count for default branch using the participation API."""
    data = api_get(f"/repos/{owner}/{repo}/stats/participation")
    if data and "all" in data:
        return sum(data["all"])
    # Fallback: use commits API with per_page=1 and parse Link header
    return 0


def fetch_open_issues_prs(owner: str, repo: str) -> tuple[int, int]:
    """Fetch open issue and PR counts."""
    issues = api_get(f"/repos/{owner}/{repo}/issues?state=open&per_page=1")
    prs = api_get(f"/repos/{owner}/{repo}/pulls?state=open&per_page=1")
    issue_count = 0
    pr_count = 0
    if isinstance(issues, list):
        # The issues endpoint includes PRs, but we'll use open_issues_count from repo data
        issue_count = len(issues)
    if isinstance(prs, list):
        pr_count = len(prs)
    return issue_count, pr_count


def relative_time(iso_str: str | None) -> str:
    """Convert ISO timestamp to relative time string."""
    if not iso_str:
        return "—"
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    delta = now - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours}h ago"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks}w ago"
    if days < 365:
        months = days // 30
        return f"{months}mo ago"
    years = days // 365
    return f"{years}y ago"


def activity_bar(pushed_at: str | None) -> str:
    """Generate a visual activity indicator based on recency."""
    if not pushed_at:
        return "⬜⬜⬜⬜⬜"
    dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days = (now - dt).days
    if days <= 1:
        return "🟩🟩🟩🟩🟩"
    if days <= 7:
        return "🟩🟩🟩🟩⬜"
    if days <= 14:
        return "🟩🟩🟩⬜⬜"
    if days <= 30:
        return "🟨🟨⬜⬜⬜"
    if days <= 90:
        return "🟧⬜⬜⬜⬜"
    return "⬜⬜⬜⬜⬜"


def status_badge(pushed_at: str | None) -> str:
    """Return a status label based on last push."""
    if not pushed_at:
        return "🔴 Inactive"
    dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days = (now - dt).days
    if days <= 7:
        return "🟢 Active"
    if days <= 30:
        return "🟡 Recent"
    if days <= 90:
        return "🟠 Slow"
    return "🔴 Inactive"


def generate_dashboard(repos: list[dict]) -> str:
    """Generate the full markdown dashboard."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")

    # Aggregate stats
    total_repos = len(repos)
    total_issues = sum(r.get("open_issues_count", 0) for r in repos)
    languages = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1

    active_repos = sum(
        1 for r in repos
        if r.get("pushed_at") and (now - datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))).days <= 30
    )

    lines: list[str] = []

    # Header
    lines.append(f"<div align=\"center\">\n")
    lines.append(f"# 🏥 Colombo South Teaching Hospital Projects\n")
    lines.append(f"**A student-led organization from the University of Sri Jayewardenepura**")
    lines.append(f"**developing software solutions for Colombo South Teaching Hospital, Kalubowila, Sri Lanka.**\n")
    lines.append(f"[![Org](https://img.shields.io/badge/GitHub-CSTH--Projects-181717?style=for-the-badge&logo=github)](https://github.com/CSTH-Projects)")
    lines.append(f"[![Location](https://img.shields.io/badge/📍-Sri_Lanka-success?style=for-the-badge)](https://github.com/CSTH-Projects)\n")
    lines.append(f"</div>\n")

    # Overview stats cards
    lines.append(f"---\n")
    lines.append(f"## 📊 Organization at a Glance\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| **Total Repositories** | {total_repos} |")
    lines.append(f"| **Active Repositories** (last 30 days) | {active_repos} |")
    lines.append(f"| **Open Issues + PRs** | {total_issues} |")
    lines.append(f"| **Languages Used** | {', '.join(f'{LANG_EMOJIS.get(l, \"📦\")} {l}' for l in sorted(languages, key=lambda x: -languages[x]))} |")
    lines.append(f"| **Last Dashboard Update** | {date_str} |")
    lines.append(f"")

    # Repository table
    lines.append(f"---\n")
    lines.append(f"## 🗂️ Repository Overview\n")
    lines.append(f"| Repository | Language | Status | Activity | Last Push | Open Issues |")
    lines.append(f"|------------|----------|--------|----------|-----------|-------------|")

    for repo in repos:
        name = repo["name"]
        desc = repo.get("description") or ""
        lang = repo.get("language") or "—"
        pushed = repo.get("pushed_at")
        issues = repo.get("open_issues_count", 0)
        archived = repo.get("archived", False)

        if archived:
            status = "📦 Archived"
        else:
            status = status_badge(pushed)

        activity = activity_bar(pushed)
        last_push = relative_time(pushed)
        lang_emoji = LANG_EMOJIS.get(lang, "")

        name_display = f"**{name}**"
        if desc:
            name_display += f"<br><sub>{desc[:60]}{'...' if len(desc) > 60 else ''}</sub>"

        lines.append(f"| {name_display} | {lang_emoji} {lang} | {status} | {activity} | {last_push} | {issues} |")

    lines.append(f"")

    # Commit activity section
    lines.append(f"---\n")
    lines.append(f"## 📈 Recent Activity\n")
    lines.append(f"| Repository | Recent Commits (52w) | Frequency |")
    lines.append(f"|------------|---------------------|-----------|")

    for repo in repos:
        if repo.get("archived"):
            continue
        name = repo["name"]
        owner = repo["owner"]["login"]
        commit_count = fetch_repo_commits_count(owner, name)
        if commit_count > 0:
            weekly_avg = commit_count / 52
            if weekly_avg >= 5:
                freq = "🔥 Very Active"
            elif weekly_avg >= 2:
                freq = "✅ Steady"
            elif weekly_avg >= 0.5:
                freq = "🐢 Occasional"
            else:
                freq = "💤 Low"
            bar_len = min(commit_count // 10, 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"| **{name}** | `{bar}` {commit_count} | {freq} |")

    lines.append(f"")

    # Language distribution
    lines.append(f"---\n")
    lines.append(f"## 🈷️ Language Distribution\n")
    total_lang_count = sum(languages.values())
    for lang, count in sorted(languages.items(), key=lambda x: -x[1]):
        pct = count / total_lang_count * 100
        color = LANG_COLORS.get(lang, "999999")
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"![{lang}](https://img.shields.io/badge/-{lang.replace(' ', '%20')}-{color}?style=flat-square) `{bar}` {count} repos ({pct:.0f}%)\n")

    # Footer
    lines.append(f"---\n")
    lines.append(f"<div align=\"center\">\n")
    lines.append(f"<sub>📊 This dashboard is auto-generated by a GitHub Action and updates on every push to any org repository.</sub>\n")
    lines.append(f"<sub>Last updated: **{date_str}**</sub>\n")
    lines.append(f"</div>\n")

    return "\n".join(lines)


def main():
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN not set. Only public repos will be visible.", file=sys.stderr)

    print(f"Fetching repos for {ORG_NAME}...", file=sys.stderr)
    repos = fetch_all_repos()

    if not repos:
        print("No repos found or API error.", file=sys.stderr)
        sys.exit(1)

    # Filter out .github repo itself to avoid self-reference
    repos = [r for r in repos if r["name"] != ".github"]

    print(f"Found {len(repos)} repositories.", file=sys.stderr)

    dashboard = generate_dashboard(repos)

    if "--stdout" in sys.argv:
        print(dashboard)
    else:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            f.write(dashboard)
        print(f"✅ Dashboard written to {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
