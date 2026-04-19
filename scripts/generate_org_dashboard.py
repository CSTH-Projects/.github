#!/usr/bin/env python3
"""
CSTH-Projects Organization Dashboard Generator

Fetches repo metadata from the GitHub API and generates a professional
profile/README.md with Mermaid charts, commit details, PR/issue data,
and security alert counts.

Exposes ONLY metadata — no source code, no secrets. Safe for public view.

Usage:
    python generate_org_dashboard.py              # writes profile/README.md
    python generate_org_dashboard.py --stdout      # prints to stdout

Required env:
    GITHUB_TOKEN  — PAT with read:org, repo (metadata), security_events scope
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

# ── Language colors for shields.io badges ────────────────────────────────
LANG_COLORS: dict[str, str] = {
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
    "Ruby": "CC342D",
    "PHP": "4F5D95",
    "Kotlin": "A97BFF",
    "Swift": "F05138",
    "Dart": "0175C2",
}


# ═══════════════════════════════════════════════════════════════════════════
# API helpers
# ═══════════════════════════════════════════════════════════════════════════

def api_get(path: str) -> Any:
    """Authenticated GET to GitHub API. Returns parsed JSON or None."""
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
        print(f"  API {e.code} for {path}: {e.reason}", file=sys.stderr)
        return None


def api_get_link_count(path: str) -> int:
    """GET a paginated endpoint with per_page=1 and parse total from Link header."""
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
            link = resp.headers.get("Link", "")
            # Parse last page from Link: <...?page=42>; rel="last"
            if 'rel="last"' in link:
                for part in link.split(","):
                    if 'rel="last"' in part:
                        page_str = part.split("page=")[-1].split(">")[0]
                        return int(page_str)
            # No pagination = the items fit in one page
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return len(data)
            return 0
    except urllib.error.HTTPError:
        return 0


# ═══════════════════════════════════════════════════════════════════════════
# Data fetchers
# ═══════════════════════════════════════════════════════════════════════════

def fetch_all_repos() -> list[dict]:
    """Fetch all org repos (paginated), sorted by most recently pushed."""
    repos: list[dict] = []
    page = 1
    while True:
        data = api_get(
            f"/orgs/{ORG_NAME}/repos?per_page=100&page={page}"
            f"&sort=pushed&direction=desc"
        )
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


def fetch_participation(owner: str, repo: str) -> dict:
    """Get 52-week participation stats (all commits + owner commits)."""
    data = api_get(f"/repos/{owner}/{repo}/stats/participation")
    if data and "all" in data:
        return {
            "total_52w": sum(data["all"]),
            "owner_52w": sum(data.get("owner", [])),
            "weekly": data["all"],
        }
    return {"total_52w": 0, "owner_52w": 0, "weekly": []}


def fetch_latest_commit(owner: str, repo: str) -> dict | None:
    """Fetch the most recent commit on the default branch."""
    data = api_get(f"/repos/{owner}/{repo}/commits?per_page=1")
    if data and isinstance(data, list) and len(data) > 0:
        c = data[0]
        return {
            "sha": c["sha"][:7],
            "message": (c["commit"]["message"].split("\n")[0])[:60],
            "author": c["commit"]["author"]["name"],
            "date": c["commit"]["author"]["date"],
        }
    return None


def fetch_open_prs(owner: str, repo: str) -> list[dict]:
    """Fetch open pull requests (up to 10)."""
    data = api_get(f"/repos/{owner}/{repo}/pulls?state=open&per_page=10&sort=updated&direction=desc")
    if not data or not isinstance(data, list):
        return []
    results = []
    for pr in data:
        results.append({
            "number": pr["number"],
            "title": (pr["title"])[:50],
            "author": pr["user"]["login"],
            "updated": pr["updated_at"],
            "draft": pr.get("draft", False),
        })
    return results


def fetch_total_commit_count(owner: str, repo: str) -> int:
    """Get total number of commits on default branch."""
    return api_get_link_count(f"/repos/{owner}/{repo}/commits?per_page=1")


def fetch_total_pr_counts(owner: str, repo: str) -> tuple[int, int]:
    """Returns (open_prs, closed_prs) counts."""
    open_count = api_get_link_count(f"/repos/{owner}/{repo}/pulls?state=open&per_page=1")
    closed_count = api_get_link_count(f"/repos/{owner}/{repo}/pulls?state=closed&per_page=1")
    return open_count, closed_count


def fetch_total_issue_counts(owner: str, repo: str) -> tuple[int, int]:
    """Returns (open_issues, closed_issues) — excluding PRs is not exact via API."""
    open_count = api_get_link_count(f"/repos/{owner}/{repo}/issues?state=open&per_page=1")
    closed_count = api_get_link_count(f"/repos/{owner}/{repo}/issues?state=closed&per_page=1")
    return open_count, closed_count


def fetch_languages(owner: str, repo: str) -> dict[str, int]:
    """Fetch byte-count breakdown of languages in the repo."""
    data = api_get(f"/repos/{owner}/{repo}/languages")
    if data and isinstance(data, dict):
        return data
    return {}


def fetch_contributors(owner: str, repo: str) -> list[dict]:
    """Fetch top contributors (up to 10)."""
    data = api_get(f"/repos/{owner}/{repo}/contributors?per_page=10")
    if data and isinstance(data, list):
        return [{"login": c["login"], "contributions": c["contributions"]} for c in data]
    return []


def fetch_security_alerts_count(owner: str, repo: str) -> int:
    """Fetch open Dependabot alert count (requires security_events scope)."""
    data = api_get(f"/repos/{owner}/{repo}/dependabot/alerts?state=open&per_page=1")
    if isinstance(data, list):
        return api_get_link_count(
            f"/repos/{owner}/{repo}/dependabot/alerts?state=open&per_page=1"
        )
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# Formatting helpers
# ═══════════════════════════════════════════════════════════════════════════

def relative_time(iso_str: str | None) -> str:
    if not iso_str:
        return "n/a"
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    delta = now - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            mins = delta.seconds // 60
            return f"{mins}m ago" if mins > 0 else "just now"
        return f"{hours}h ago"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        return f"{days // 7}w ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def status_label(pushed_at: str | None, archived: bool = False) -> str:
    if archived:
        return "Archived"
    if not pushed_at:
        return "Inactive"
    dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    days = (datetime.now(timezone.utc) - dt).days
    if days <= 7:
        return "Active"
    if days <= 30:
        return "Recent"
    if days <= 90:
        return "Slow"
    return "Inactive"


def status_shield(status: str) -> str:
    """Shields.io badge for status."""
    color_map = {
        "Active": "brightgreen",
        "Recent": "yellow",
        "Slow": "orange",
        "Inactive": "red",
        "Archived": "lightgrey",
    }
    color = color_map.get(status, "lightgrey")
    return f"![{status}](https://img.shields.io/badge/{status}-{color}?style=flat-square)"


def frequency_label(total_52w: int) -> str:
    avg = total_52w / 52
    if avg >= 5:
        return "Very Active"
    if avg >= 2:
        return "Steady"
    if avg >= 0.5:
        return "Occasional"
    if total_52w > 0:
        return "Low"
    return "None"


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard generator
# ═══════════════════════════════════════════════════════════════════════════

def generate_dashboard(repos: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y at %H:%M UTC")

    # ── Collect enriched data per repo ───────────────────────────────────
    repo_data: list[dict] = []
    all_languages: dict[str, int] = {}  # language -> total bytes across all repos
    total_commits_all = 0
    total_open_prs_all = 0
    total_closed_prs_all = 0
    total_open_issues_all = 0
    total_closed_issues_all = 0
    total_security_alerts = 0
    max_commits_52w = 1  # for normalization

    for repo in repos:
        owner = repo["owner"]["login"]
        name = repo["name"]
        print(f"  Fetching data for {name}...", file=sys.stderr)

        participation = fetch_participation(owner, name)
        latest = fetch_latest_commit(owner, name)
        total_commits = fetch_total_commit_count(owner, name)
        open_prs, closed_prs = fetch_total_pr_counts(owner, name)
        open_issues, closed_issues = fetch_total_issue_counts(owner, name)
        langs = fetch_languages(owner, name)
        contributors = fetch_contributors(owner, name)
        security = fetch_security_alerts_count(owner, name)

        for lang, byte_count in langs.items():
            all_languages[lang] = all_languages.get(lang, 0) + byte_count

        total_commits_all += total_commits
        total_open_prs_all += open_prs
        total_closed_prs_all += closed_prs
        total_open_issues_all += open_issues
        total_closed_issues_all += closed_issues
        total_security_alerts += security

        if participation["total_52w"] > max_commits_52w:
            max_commits_52w = participation["total_52w"]

        rd = {
            "name": name,
            "description": repo.get("description") or "",
            "language": repo.get("language") or "n/a",
            "pushed_at": repo.get("pushed_at"),
            "created_at": repo.get("created_at"),
            "archived": repo.get("archived", False),
            "default_branch": repo.get("default_branch", "main"),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "size_kb": repo.get("size", 0),
            "total_commits": total_commits,
            "participation": participation,
            "latest_commit": latest,
            "open_prs": open_prs,
            "closed_prs": closed_prs,
            "open_issues": open_issues,
            "closed_issues": closed_issues,
            "languages": langs,
            "contributors": contributors,
            "security_alerts": security,
        }
        repo_data.append(rd)

    # ── Calculate org-wide stats ─────────────────────────────────────────
    total_repos = len(repo_data)
    active_count = sum(1 for r in repo_data if status_label(r["pushed_at"], r["archived"]) == "Active")
    total_contributors = len({
        c["login"] for r in repo_data for c in r["contributors"]
    })
    unique_languages = sorted(all_languages.keys(), key=lambda x: -all_languages[x])

    lines: list[str] = []

    # ── REPOSITORY OVERVIEW (Section 1) ───────────────────────────────────
    lines.append("## Repository Overview\n")
    lines.append(
        "| Repository | Status | Language | Commits | "
        "Latest Commit | Author | Last Push |"
    )
    lines.append(
        "|------------|--------|----------|---------|"
        "---------------|--------|-----------|"
    )

    for r in repo_data:
        status = status_label(r["pushed_at"], r["archived"])
        badge = status_shield(status)
        lc = r["latest_commit"]
        if lc:
            sha_display = f"`{lc['sha']}`"
            msg = lc["message"]
            if len(msg) > 45:
                msg = msg[:42] + "..."
            commit_display = f"{sha_display} {msg}"
            author = lc["author"]
        else:
            commit_display = "n/a"
            author = "n/a"

        name_display = f"**{r['name']}**"
        if r["description"]:
            desc = r["description"]
            if len(desc) > 55:
                desc = desc[:52] + "..."
            name_display += f"<br><sub>{desc}</sub>"

        lines.append(
            f"| {name_display} | {badge} | {r['language']} | "
            f"{r['total_commits']:,} | {commit_display} | "
            f"{author} | {relative_time(r['pushed_at'])} |"
        )
    lines.append("")

    # ── COMMIT ACTIVITY (Section 2 — Mermaid Bar Chart) ─────────────────
    lines.append("---\n")
    lines.append("## Commit Activity (Last 52 Weeks)\n")
    lines.append("```mermaid")
    lines.append("xychart-beta")
    lines.append('    title "Weekly Commits Across All Repositories"')
    lines.append('    x-axis "Weeks ago" [52, 48, 44, 40, 36, 32, 28, 24, 20, 16, 12, 8, 4, 1]')

    # Aggregate weekly commits across all repos (52 weeks)
    weekly_totals = [0] * 52
    for r in repo_data:
        weekly = r["participation"].get("weekly", [])
        for i, val in enumerate(weekly):
            if i < 52:
                weekly_totals[i] += val

    # Sample at the positions shown on x-axis
    sample_indices = [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 51]
    sampled = [weekly_totals[i] if i < len(weekly_totals) else 0 for i in sample_indices]
    values_str = ", ".join(str(v) for v in sampled)
    lines.append(f'    y-axis "Commits"')
    lines.append(f'    bar [{values_str}]')
    lines.append("```\n")

    # Per-repo commit frequency (Mermaid horizontal bar)
    non_archived = [r for r in repo_data if not r.get("archived")]
    if non_archived:
        lines.append("```mermaid")
        lines.append("xychart-beta horizontal")
        lines.append('    title "Commits per Repository (52 Weeks)"')
        repo_names = [r["name"] for r in non_archived]
        repo_commits = [r["participation"]["total_52w"] for r in non_archived]
        names_str = ", ".join(f'"{n}"' for n in repo_names)
        commits_str = ", ".join(str(c) for c in repo_commits)
        lines.append(f'    x-axis [{names_str}]')
        lines.append(f'    y-axis "Commits"')
        lines.append(f'    bar [{commits_str}]')
        lines.append("```\n")

    lines.append("| Repository | Commits (52w) | Frequency |")
    lines.append("|------------|---------------|-----------|")
    for r in non_archived:
        c52 = r["participation"]["total_52w"]
        freq = frequency_label(c52)
        lines.append(f"| **{r['name']}** | {c52} | {freq} |")
    lines.append("")

    # ── ORGANIZATION SUMMARY (Section 3) ─────────────────────────────────
    lines.append("---\n")
    lines.append("## Organization Summary\n")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Repositories | {total_repos} |")
    lines.append(f"| Active (last 7 days) | {active_count} |")
    lines.append(f"| Total Commits | {total_commits_all:,} |")
    lines.append(f"| Open Pull Requests | {total_open_prs_all} |")
    lines.append(f"| Merged/Closed Pull Requests | {total_closed_prs_all} |")
    lines.append(f"| Open Issues | {total_open_issues_all} |")
    lines.append(f"| Closed Issues | {total_closed_issues_all} |")
    lines.append(f"| Security Alerts | {total_security_alerts} |")
    lines.append(f"| Contributors | {total_contributors} |")
    lang_display = ", ".join(unique_languages[:8])
    if len(unique_languages) > 8:
        lang_display += f", +{len(unique_languages) - 8} more"
    lines.append(f"| Languages | {lang_display} |")
    lines.append(f"| Last Updated | {date_str} |")
    lines.append("")

    # ── LANGUAGE DISTRIBUTION (Section 4 — Mermaid Pie Chart) ────────────
    lines.append("---\n")
    lines.append("## Language Distribution\n")
    total_bytes = sum(all_languages.values()) or 1
    sorted_langs = sorted(all_languages.items(), key=lambda x: -x[1])
    top_langs = sorted_langs[:8]
    other_bytes = sum(v for _, v in sorted_langs[8:])

    lines.append("```mermaid")
    lines.append("pie showData")
    lines.append('    title Codebase Language Breakdown (by bytes)')
    for lang, byte_count in top_langs:
        pct = byte_count / total_bytes * 100
        lines.append(f'    "{lang}" : {pct:.1f}')
    if other_bytes > 0:
        lines.append(f'    "Other" : {other_bytes / total_bytes * 100:.1f}')
    lines.append("```\n")

    for lang, byte_count in top_langs:
        pct = byte_count / total_bytes * 100
        color = LANG_COLORS.get(lang, "999999")
        safe_name = lang.replace(" ", "%20").replace("#", "%23")
        lines.append(
            f"![{lang}](https://img.shields.io/badge/{safe_name}-{pct:.1f}%25-{color}?style=flat-square)"
        )
    lines.append("\n")

    # ── PULL REQUESTS & ISSUES (Section 5) ───────────────────────────────
    lines.append("---\n")
    lines.append("## Pull Requests and Issues\n")
    lines.append(
        "| Repository | PRs (Open) | PRs (Closed) | "
        "Issues (Open) | Issues (Closed) | Security Alerts |"
    )
    lines.append(
        "|------------|------------|--------------|"
        "---------------|-----------------|-----------------|"
    )
    for r in repo_data:
        alert_display = str(r["security_alerts"])
        if r["security_alerts"] > 0:
            alert_display = f"**{r['security_alerts']}**"
        lines.append(
            f"| **{r['name']}** | {r['open_prs']} | {r['closed_prs']} | "
            f"{r['open_issues']} | {r['closed_issues']} | {alert_display} |"
        )
    lines.append("")

    # ── PR/Issue Mermaid chart ───────────────────────────────────────────
    if total_open_prs_all + total_closed_prs_all + total_open_issues_all + total_closed_issues_all > 0:
        lines.append("```mermaid")
        lines.append("pie showData")
        lines.append('    title "PRs and Issues Across Organization"')
        if total_open_prs_all > 0:
            lines.append(f'    "Open PRs" : {total_open_prs_all}')
        if total_closed_prs_all > 0:
            lines.append(f'    "Closed PRs" : {total_closed_prs_all}')
        if total_open_issues_all > 0:
            lines.append(f'    "Open Issues" : {total_open_issues_all}')
        if total_closed_issues_all > 0:
            lines.append(f'    "Closed Issues" : {total_closed_issues_all}')
        lines.append("```\n")

    # ── CONTRIBUTORS (Section 6 — Mermaid Bar Chart) ─────────────────────
    lines.append("---\n")
    lines.append("## Top Contributors\n")

    # Aggregate contributions across repos
    contributor_totals: dict[str, int] = {}
    for r in repo_data:
        for c in r["contributors"]:
            login = c["login"]
            contributor_totals[login] = contributor_totals.get(login, 0) + c["contributions"]

    sorted_contributors = sorted(contributor_totals.items(), key=lambda x: -x[1])[:15]
    if sorted_contributors:
        # Mermaid horizontal bar chart for contributions
        lines.append("```mermaid")
        lines.append("xychart-beta horizontal")
        lines.append('    title "Contributions by Developer"')
        contributor_names = [sc[0] for sc in sorted_contributors]
        contributor_counts = [sc[1] for sc in sorted_contributors]
        names_str = ", ".join(f'"{n}"' for n in contributor_names)
        counts_str = ", ".join(str(c) for c in contributor_counts)
        lines.append(f'    x-axis [{names_str}]')
        lines.append(f'    y-axis "Contributions"')
        lines.append(f'    bar [{counts_str}]')
        lines.append("```\n")

        # Also show the data table
        lines.append("| Rank | Contributor | Contributions |")
        lines.append("|------|-------------|---------------|")
        for i, (login, count) in enumerate(sorted_contributors, 1):
            lines.append(f"| {i} | `{login}` | {count:,} |")
        lines.append("")

    # ── PER-REPO LANGUAGE BREAKDOWN ──────────────────────────────────────
    lines.append("---\n")
    lines.append("## Per-Repository Language Breakdown\n")
    for r in repo_data:
        if not r["languages"]:
            continue
        total = sum(r["languages"].values()) or 1
        sorted_repo_langs = sorted(r["languages"].items(), key=lambda x: -x[1])
        badges = []
        for lang, byte_count in sorted_repo_langs[:5]:
            pct = byte_count / total * 100
            color = LANG_COLORS.get(lang, "999999")
            safe_name = lang.replace(" ", "%20").replace("#", "%23")
            badges.append(
                f"![{lang}](https://img.shields.io/badge/{safe_name}-{pct:.0f}%25-{color}?style=flat-square)"
            )
        lines.append(f"**{r['name']}**: {' '.join(badges)}  ")
    lines.append("")

    # ── FOOTER ───────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append('<div align="center">\n')
    lines.append(f"<sub>Auto-generated on {date_str}.</sub>")
    lines.append(
        "<sub>Updates automatically on every push, PR, issue, or security event "
        "across all organization repositories.</sub>\n"
    )
    lines.append("</div>\n")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    if not GITHUB_TOKEN:
        print("WARNING: GITHUB_TOKEN not set. Only public repos visible.", file=sys.stderr)

    print(f"Fetching repos for {ORG_NAME}...", file=sys.stderr)
    repos = fetch_all_repos()

    if not repos:
        print("No repos found or API error.", file=sys.stderr)
        sys.exit(1)

    # Filter out .github repo itself
    repos = [r for r in repos if r["name"] != ".github"]

    print(f"Found {len(repos)} repositories. Fetching details...", file=sys.stderr)

    dashboard = generate_dashboard(repos)

    if "--stdout" in sys.argv:
        print(dashboard)
    else:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            f.write(dashboard)
        print(f"Dashboard written to {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
