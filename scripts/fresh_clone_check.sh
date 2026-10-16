#!/usr/bin/env bash
# What someone arriving at the repository does, checked on a fresh clone (CT-0096):
#
#     scripts/fresh_clone_check.sh [branch] [repository]
#
# Clones the branch (default: the current one) from the repository (default: origin's URL) into a temporary
# folder, then runs `make setup`, `make demo`, `make test` and `make build` there, the demos in the same
# temporary folder -- nothing outside it is written. Prints each step's time and stops at the first that fails.
# About fifteen minutes, with the network; not part of the suite. Run it before showing the repository.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
branch="${1:-$(git -C "$here" rev-parse --abbrev-ref HEAD)}"
repository="${2:-$(git -C "$here" remote get-url origin)}"
work="$(mktemp -d -t ct-fresh-clone-XXXXXX)"
echo "==> A fresh clone of $branch from $repository in $work"

step() {
  local name="$1"; shift
  local started=$SECONDS
  if "$@" >"$work/$name.log" 2>&1; then
    echo "ok    $name  ($((SECONDS - started)) s)"
  else
    echo "FAIL  $name  ($((SECONDS - started)) s) -- the end of $work/$name.log:"
    tail -25 "$work/$name.log"
    exit 1
  fi
}

step clone git clone --quiet --branch "$branch" "$repository" "$work/repo"
cd "$work/repo"
step setup make setup
step demo make demo DEMOS="$work/demos"
step test make test
step build make build DEMOS="$work/demos"
grep -E "^(OK|FAILED)" "$work/test.log" || true
echo "==> Done: a fresh clone sets up, makes its demos, passes its suite and builds the reel. ($work)"
