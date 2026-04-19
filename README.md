# CSTH-Projects Organization Profile

This repo powers the [CSTH-Projects organization profile page](https://github.com/CSTH-Projects).

## How It Works

- `profile/README.md` — Displayed on the org's Overview tab (auto-generated)
- `scripts/generate_org_dashboard.py` — Fetches repo metadata via GitHub API and generates the dashboard
- `.github/workflows/update-dashboard.yml` — Runs daily at 6:00 UTC + manual trigger

## Setup

### 1. Create a Personal Access Token (PAT)

1. Go to **GitHub > Settings > Developer Settings > Fine-grained Personal Access Tokens**
2. Create a new token with:
   - **Resource owner**: `CSTH-Projects`
   - **Repository access**: All repositories
   - **Permissions**: `Metadata` (read-only) — this is the minimum needed
3. Copy the token

### 2. Add the secret to this repo

1. Go to this repo's **Settings > Secrets and variables > Actions**
2. Click **New repository secret**
3. Name: `ORG_DASHBOARD_TOKEN`
4. Value: paste the PAT from step 1

### 3. Run the workflow

1. Go to **Actions** tab in this repo
2. Click **Update Org Dashboard** workflow
3. Click **Run workflow**
4. The `profile/README.md` will be auto-updated with live data

After this, the dashboard will auto-refresh daily and whenever you manually trigger it.

## What's Displayed (Safe for Public)

Only metadata is shown — **zero source code is exposed**:

- Repository names and descriptions
- Primary language per repo
- Last push date (relative time)
- Open issues/PR count
- Commit frequency (last 52 weeks)
- Activity status badges (🟢 Active → 🔴 Inactive)
- Language distribution chart

## Adding Live Updates from Other Repos

To trigger a dashboard refresh whenever you push to any org repo, add this to that repo's CI workflow:

```yaml
# Add to any org repo's .github/workflows/ci.yml
- name: Trigger org dashboard update
  if: github.ref == 'refs/heads/main'
  run: |
    curl -X POST \
      -H "Authorization: Bearer ${{ secrets.ORG_DASHBOARD_TOKEN }}" \
      -H "Accept: application/vnd.github+json" \
      https://api.github.com/repos/CSTH-Projects/.github/dispatches \
      -d '{"event_type": "repo-updated"}'
```
