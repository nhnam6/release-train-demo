# Real-GitHub demo — tag-based release train

This is the same mechanics as `_docs/deca-pages/release_tag/RELEASE_PLAN.md`, but wired
into **real GitHub Actions on a real (throwaway) repo** instead of local bash. Everything
git/GitHub-side is genuine: `release-please`, branch/tag rulesets, required status checks,
the guard job, the `production` pointer branch. The only thing faked is the AWS deploy step
(`deploy` job in `release-deploy.yml`) — no CDK/Copilot here, just an `echo`.

**You run every `git push` / `gh repo create` / `gh api` command yourself.** This doc only
prepares files and gives you the exact commands — nothing here touches GitHub on its own.

Bonus: this also **answers a real open question** from RELEASE_PLAN.md §6.1 — does
`release-please`'s `release-type: python` actually bump `[tool.poetry] version` correctly?
`release-please-config.json` here is byte-for-byte the config proposed for `deca-pages-api`.
Watch what its first Release PR does to `pyproject.toml`.

> **Bugs this demo already caught, running for real** (kept here, not swept under the rug):
> - The first Release PR's checklist run silently posted nothing — assumed a previous tag
>   always exists to diff from, false on a repo's first-ever release. Fixed with a root-commit
>   fallback. Only bites once, on release #1.
> - The checklist diffed against the Release PR branch's own `HEAD` — wrong: `release-please`
>   only rebases that branch when a new commit parses as a conventional-commit type it tracks;
>   a commit it doesn't recognize (GitHub's own auto-revert message, `Revert "..." (#N)`) lands
>   on `main` but the branch silently stays behind it. Fixed to diff against `origin/main`,
>   the only source that's always current.
> - **Biggest one:** `release-deploy.yml` never fired at all. A tag pushed by the default
>   `GITHUB_TOKEN` (release-please's own tag) doesn't trigger `on: push: tags:` — same
>   anti-recursion rule as the PR case below, just hitting the demo's central mechanism
>   instead of a side one. Added `workflow_dispatch` as the manual escape hatch (§3 step 4
>   now uses it). The real repo's GitHub App token avoids this for tags too, same as it does
>   for PRs.

---

## 0. Prerequisites

- `gh` CLI installed and logged in (`gh auth status`)
- OK with creating a small **private** repo under your own GitHub account (or a sandbox org) —
  this needs real Actions minutes and a real repo, there's no way around that for "giống thật"

## 1. Push it

```bash
cd _docs/deca-pages/release_tag/demo/github

git init -q -b main
git config user.name  "<your name>"
git config user.email "<your email>"
git add -A
git commit -q -m "chore: seed demo-service at 0.1.0"

gh repo create deca-release-train-demo --private --source=. --remote=origin --push
```

That last command creates the GitHub repo **and** pushes `main` in one step.

**Required before anything else runs:** new repos default to *not* letting Actions open
PRs — `release-please` needs to, on the very first push to `main`. Without this, its run
fails with `GitHub Actions is not permitted to create or approve pull requests.`

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

gh api -X PUT "repos/$REPO/actions/permissions/workflow" --input - <<'EOF'
{
  "default_workflow_permissions": "write",
  "can_approve_pull_request_reviews": true
}
EOF
```
Same toggle on github.com: **Settings → Actions → General → Workflow permissions** →
*Read and write permissions* + check *Allow GitHub Actions to create and approve pull
requests* → Save. Hit the error anyway because you pushed before reading this far? Re-run
the failed job: `gh run rerun $(gh run list --workflow=release-please.yml --limit 1 --json databaseId -q '.[0].databaseId')`.

## 2. Turn on branch protection (once)

Required status check on `main`, plus a tag ruleset so no one can hand-tag or delete a
release tag — this is G3/G4 from RELEASE_PLAN.md, for real:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# Require the CI check + a PR (no direct pushes) on main
gh api "repos/$REPO/rulesets" --input - <<'EOF'
{
  "name": "Protect main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["squash"]
      }
    },
    { "type": "non_fast_forward" },
    {
      "type": "required_status_checks",
      "parameters": {
        "required_status_checks": [ { "context": "test" } ],
        "strict_required_status_checks_policy": false
      }
    }
  ]
}
EOF

# Tags v* are immutable: no delete, no force-push over an existing tag
gh api "repos/$REPO/rulesets" --input - <<'EOF'
{
  "name": "Protect release tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/tags/v*"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" }
  ]
}
EOF
```

`required_approving_review_count: 0` is deliberate for this **solo** demo repo — you have
no second account to approve your own PRs with. The real repo keeps the org's `2 approvals`.

If the first call 422s complaining the `test` status check doesn't exist yet — GitHub won't
let you require a check that has never reported once. Drop the `required_status_checks` rule
from the payload, run one PR through CI (§3 below), then re-run the call with it added back.

## 3. Scenario: happy path (RELEASE_PLAN.md §13.1)

```bash
git checkout -q -b feat/hello
echo 'def hello(): return "hi"' >> app.py
git add app.py && git commit -q -m "feat: add a hello helper"
git push -q -u origin feat/hello
gh pr create --fill --base main
gh pr merge --squash --auto   # or click Merge on github.com once CI is green
```

Watch on GitHub:
1. **Actions tab** — `CI` runs on your PR, `Release Please` runs right after it merges to `main`.
2. **Pull requests tab** — a new PR appears, opened by `release-please[bot]`: *"chore(main):
   release 0.2.0"* (or similar), with `pyproject.toml`'s version bumped and a `CHANGELOG.md`
   generated. **This is the answer to the open question** — check the diff shows
   `version = "0.2.0"` under `[tool.poetry]`, not left untouched.
3. Its `CI` and `Release Checklist` runs land as **`action_required`** in the Actions tab
   instead of running — expected, not a bug. Both trigger on `pull_request`, but the PR was
   opened by the default `GITHUB_TOKEN`, and GitHub gates `pull_request`-triggered runs
   behind manual approval when the actor is a bot rather than blocking them outright. This
   is exactly the gap flagged in RELEASE_PLAN.md §8 Q4 — the real repo needs a GitHub App
   token to avoid the friction. Approve them for real:
   ```bash
   REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
   gh run list --json databaseId,name,status -q '.[] | select(.status=="action_required")'
   gh api -X POST "repos/$REPO/actions/runs/<run-id>/approve"   # once per pending run
   ```
   or click **Approve and run** on the run's page. Once approved, `Release Checklist` posts
   a comment with the auto-generated change list + impact flags.
4. **Merge that Release PR.** A `v0.2.0` tag appears (Tags tab) and a GitHub Release is
   published (Releases tab) — but `Release Deploy` **won't start on its own**: the tag was
   pushed by `GITHUB_TOKEN`, same anti-recursion issue as step 3, now hitting `on: push:
   tags:` instead of `on: pull_request:`. Trigger it by hand:
   ```bash
   gh workflow run release-deploy.yml --repo "$REPO" -f tag=v0.2.0
   ```
   Unlike steps 3/4's PR-triggered runs, this one runs immediately — no approval needed,
   since you're calling `workflow_dispatch` directly as yourself, not through a bot-authored
   event. Watch `guard` (real check against the tag), `deploy` (stub), `promote` (real `git
   push` fast-forwarding `production`) run in order. Confirm:
   ```bash
   git fetch origin production
   git log --oneline -1 origin/production   # should be the release commit, tagged v0.2.0
   ```

## 4. Scenario: CI red blocks merge (§13.7)

```bash
git checkout -q main && git pull -q
git checkout -q -b fix/broken
echo 'def add(a, b): return a - b' > app.py   # deliberately wrong
git add app.py && git commit -q -m "fix: this is broken on purpose"
git push -q -u origin fix/broken
gh pr create --fill --base main
```
Open the PR on github.com — the merge box is red, **Merge is disabled** (required check
failing), regardless of approvals. Fix it and push again to unblock:
```bash
echo 'def add(a, b): return a + b' > app.py
git commit -aqm "fix: revert the deliberate breakage"
git push
```

## 5. Scenario: a bad tag gets rejected (§13.5/13.6)

```bash
git checkout -q main && git pull -q
git tag v9.9.9   # doesn't match pyproject.toml's real version
git push origin v9.9.9
```
Actions tab → `Release Deploy` → `guard` job fails immediately with `GUARD FAIL: tag
'v9.9.9' != pyproject '...'`. `deploy` and `promote` never start — `production` doesn't move.
Clean up:
```bash
git push origin :refs/tags/v9.9.9
git tag -d v9.9.9
```

## 6. Scenario: hotfix while a feature is still pending (§13.8)

This one's a decision tree, not something to automate — walk it manually to feel the
actual bind: merge a `feat` to `main`, **don't** merge the Release PR yet, then cut a
hotfix and merge it. Watch the Release PR (still open) update itself to include *both*
commits — that's the bundling problem, live, not hypothetical:

```bash
git checkout -q main && git pull -q
git checkout -q -b feat/pending
echo 'def pending(): pass' >> app.py
git add app.py && git commit -q -m "feat: something not ready for QA yet"
git push -q -u origin feat/pending
gh pr create --fill --base main && gh pr merge --squash --auto

# don't touch the Release PR that just updated -- now cut a hotfix
git checkout -q main && git pull -q
git checkout -q -b hotfix/p1
echo 'def safe(): pass' > cart.py
git add cart.py && git commit -q -m "fix: prevent a null-cart crash"
git push -q -u origin hotfix/p1
gh pr create --fill --base main --label hotfix && gh pr merge --squash --auto
```
Open the Release PR now — it lists **both** the `feat` and the `fix`. Merging it ships
both. See §13.8 in the plan for the 3 ways out (flag off / owner-approved early ship /
revert-then-reapply) — none of those steps are automated here on purpose, they're a human
decision each time.

## 7. What's real vs. stubbed

| Piece | This demo | Real `deca-pages-api` design |
|---|---|---|
| `release-please` version bump / CHANGELOG / tag / Release | **Real** | Real |
| Branch + tag rulesets | **Real** | Real |
| Required status check blocking merge | **Real** | Real (multiple checks) |
| Guard job (tag == pyproject, reachable from main) | **Real** | Real |
| `production` pointer branch, fast-forwarded on deploy | **Real** | Real |
| Bot identity for Release PR / checklist / tag | default `GITHUB_TOKEN` — **CI, checklist, and `release-deploy.yml` all need a manual kick** (`gh api .../approve` or `gh workflow run`) | GitHub App token — all three fire on their own |
| `deploy` job | `echo` + `sleep 3` | CDK deploy + Copilot pipeline |
| Checklist comment | fresh comment every run | sticky comment, updated in place |

## 8. Cleanup

```bash
gh repo delete <owner>/deca-release-train-demo --yes   # deletes the real GitHub repo
cd .. && rm -rf github/.git   # if you want the local files gone too (or just leave them)
```
