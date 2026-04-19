# CSTH-Projects Organization Profile

This repo powers the [CSTH-Projects organization profile page](https://github.com/CSTH-Projects).

## Structure

```
.github/workflows/update-dashboard.yml   # Auto-update workflow (every 6h + real-time)
scripts/generate_org_dashboard.py        # Dashboard generator (Python, stdlib only)
profile/README.md                        # Auto-generated org profile page
templates/notify-dashboard.yml           # Copy this into each org repo for real-time updates
```

## What the Dashboard Shows

All data is metadata only — zero source code is exposed:

- **Organization Summary**: repo count, total commits, open/closed PRs and issues, security alerts, contributor count
- **Language Distribution**: Mermaid pie chart of codebase language breakdown (by bytes), per-repo badges
- **Repository Overview**: status badge, primary language, total commit count, latest commit SHA + message + author, last push time
- **Commit Activity**: Mermaid bar chart of weekly commits (52 weeks), per-repo frequency table with progress bars
- **Pull Requests and Issues**: open/closed PR and issue counts per repo, security alert counts, Mermaid pie chart
- **Top Contributors**: ranked table with contribution counts and progress bars
- **Per-Repo Language Breakdown**: shields.io badges per repository

## Setup

### 1. Create a Fine-Grained PAT

1. Go to [GitHub Settings > Fine-grained PATs](https://github.com/settings/personal-access-tokens/new)
2. **Token name**: `org-dashboard`
3. **Resource owner**: `CSTH-Projects`
4. **Repository access**: All repositories
5. **Permissions**:
   - `Metadata` — Read-only (required)
   - `Pull requests` — Read-only (for PR counts)
   - `Issues` — Read-only (for issue counts)
   - `Dependabot alerts` — Read-only (for security alerts, optional)
6. Generate and copy the token

### 2. Add as Organization Secret (recommended)

Adding the secret at the org level lets all repos use it for real-time dispatch:

1. Go to [CSTH-Projects Settings > Secrets > Actions](https://github.com/organizations/CSTH-Projects/settings/secrets/actions)
2. Click **New organization secret**
3. **Name**: `ORG_DASHBOARD_TOKEN`
4. **Value**: paste the PAT
5. **Repository access**: All repositories

### 3. Enable Real-Time Updates in Each Repo

Copy `templates/notify-dashboard.yml` into each org repo:

```bash
# For each repo:
cp templates/notify-dashboard.yml /path/to/repo/.github/workflows/notify-dashboard.yml
```

This triggers the dashboard to regenerate on every:
- Push to main/master/develop
- Pull request opened/closed/reopened
- Issue opened/closed/reopened
- Release published
- Dependabot alert created/dismissed/fixed

### 4. Run the Dashboard

1. Go to [Actions > Update Org Dashboard](https://github.com/CSTH-Projects/.github/actions)
2. Click **Run workflow**

After this, the dashboard runs automatically every 6 hours AND in real-time when any repo sends a dispatch event.
