#!/usr/bin/env bash
# Push this run's commit to main, retrying when another workflow pushed first.
#
#   bash scripts/ci_push.sh                         # retry; fail on a conflict
#   bash scripts/ci_push.sh nba-pipeline.yml -f trends_only=true
#                                                   # on a conflict, queue a fresh run
#
# A rejected push fetches main, rebases this commit onto it and tries again
# (4 attempts). A rebase conflict in generated data (picks.csv, nba_sim.db,
# slate.json) can't be merged by hand, so the rebase is aborted and, when a
# workflow is given, a fresh run of it is dispatched: it rebuilds everything,
# seal guardrail included, on the current main. REBASE_ARGS adds rebase
# options (the bot passes "-X theirs" for its own state file).
set -uo pipefail

for attempt in 1 2 3 4; do
  if git push origin HEAD:main; then
    exit 0
  fi
  echo "push rejected (attempt $attempt/4): main moved; rebasing onto it"
  sleep $((attempt * 5))
  git fetch origin main || continue
  # shellcheck disable=SC2086  # REBASE_ARGS is a word list on purpose
  if ! git rebase ${REBASE_ARGS:-} origin/main; then
    git rebase --abort || true
    if [ $# -gt 0 ]; then
      if gh workflow run "$@" --ref main; then
        echo "::warning::conflict with newer commits on main; queued a fresh run of $1 to rebuild on it"
        exit 0
      fi
      echo "::error::conflict with newer commits on main, and dispatching a fresh run of $1 failed"
      exit 1
    fi
    echo "::error::conflict with newer commits on main"
    exit 1
  fi
done
echo "::error::push still rejected after 4 attempts"
exit 1
