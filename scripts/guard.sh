#!/usr/bin/env bash
# Guard used by release-deploy.yml (RELEASE_PLAN.md §6.2) — identical to
# demo/scripts/guard.sh, copied in so this repo is self-contained once pushed.
# Blocks a prod deploy unless both hold:
#   1. tag == "v" + version declared in pyproject.toml AT THE TAG ITSELF
#   2. the tag is reachable from the trunk branch (default: main)
set -euo pipefail
TAG="${1:?usage: guard.sh <tag> [branch=main]}"
BRANCH="${2:-main}"

# Read version from the CONTENT AT THE TAG (git show), not the current working
# tree — matches the real job, which checks out that exact ref.
PYPROJECT_AT_TAG=$(git show "${TAG}:pyproject.toml" 2>/dev/null) || {
  echo "GUARD FAIL: pyproject.toml not found at tag '$TAG'" >&2
  exit 1
}
PYPROJECT_V=$(echo "$PYPROJECT_AT_TAG" | grep -m1 '^version' | sed -E 's/version = "([^"]+)"/\1/')
EXPECTED="v${PYPROJECT_V}"

if [ "$TAG" != "$EXPECTED" ]; then
  echo "GUARD FAIL: tag '$TAG' != pyproject '$EXPECTED'" >&2
  exit 1
fi

if ! git merge-base --is-ancestor "$TAG" "$BRANCH" 2>/dev/null; then
  echo "GUARD FAIL: '$TAG' is not reachable from '$BRANCH'" >&2
  exit 1
fi

echo "GUARD OK: $TAG matches pyproject ($EXPECTED) and is on $BRANCH"
