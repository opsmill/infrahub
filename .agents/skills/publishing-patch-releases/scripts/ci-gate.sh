#!/usr/bin/env bash
# Usage: ci-gate.sh <owner/repo> <pr-number> <max-reruns> <max-failed-checks>
#
# Waits until no check on the pull request is pending, then reruns the failed GitHub Actions jobs
# until every check passes or a limit is reached.
#
# Exit codes:
#   0   every check passed or was skipped
#   1   a gh command failed
#   2   more checks failed in one round than <max-failed-checks>
#   3   checks still failed after <max-reruns> reruns
#   4   no check appeared within CI_GATE_FIRST_CHECK_TIMEOUT seconds (20 minutes by default), or the
#       checks did not finish within CI_GATE_TIMEOUT seconds (4 hours by default)
#   5   a failed check is not a GitHub Actions job, so it cannot be rerun
#   64  wrong arguments
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <owner/repo> <pr-number> <max-reruns> <max-failed-checks>" >&2
  exit 64
fi

repo=$1
pr=$2
max_reruns=$3
max_failed=$4
interval=${CI_GATE_INTERVAL:-60}
start=$(date +%s)
deadline=$((start + ${CI_GATE_TIMEOUT:-14400}))
first_check_deadline=$((start + ${CI_GATE_FIRST_CHECK_TIMEOUT:-1200}))
reruns=0
last_status=""

log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# One line per check: bucket, name, link. `gh pr checks` exits non-zero when a check failed and
# when no check is reported yet, so only its output is used.
snapshot() {
  gh pr checks "$pr" --repo "$repo" --json bucket,name,link \
    --jq '.[] | [.bucket, .name, .link] | @tsv' 2>/dev/null || true
}

while true; do
  now=$(date +%s)
  if ((now >= deadline)); then
    log "checks did not finish in time; stopping"
    exit 4
  fi

  lines=$(snapshot)
  total=$(grep -c . <<<"$lines" || true)
  pending=$(grep -c $'^pending\t' <<<"$lines" || true)

  if ((total == 0)) && ((now >= first_check_deadline)); then
    log "no check appeared on $repo#$pr; stopping"
    exit 4
  fi
  if ((total == 0 || pending > 0)); then
    status="$pending of $total checks pending"
    if [[ $status != "$last_status" ]]; then
      log "$status"
      last_status=$status
    fi
    sleep "$interval"
    continue
  fi

  failed=$(grep -E $'^(fail|cancel)\t' <<<"$lines" || true)
  if [[ -z $failed ]]; then
    log "all $total checks passed or were skipped"
    exit 0
  fi

  count=$(grep -c . <<<"$failed")
  log "$count of $total checks failed:"
  cut -f2,3 <<<"$failed" | sed 's/^/  /'

  if ((count > max_failed)); then
    log "more than $max_failed checks failed; stopping"
    exit 2
  fi
  if ((reruns >= max_reruns)); then
    log "checks still fail after $reruns reruns; stopping"
    exit 3
  fi
  if cut -f3 <<<"$failed" | grep -qvE '/actions/runs/[0-9]+/'; then
    log "a failed check is not a GitHub Actions job and cannot be rerun; stopping"
    exit 5
  fi

  reruns=$((reruns + 1))
  while read -r run_id; do
    log "rerun $reruns of $max_reruns: failed jobs of workflow run $run_id"
    gh run rerun "$run_id" --repo "$repo" --failed </dev/null
  done < <(cut -f3 <<<"$failed" | sed -nE 's#.*/actions/runs/([0-9]+)/.*#\1#p' | sort -u)
  last_status=""
  # A rerun job takes a few seconds to show as pending again.
  sleep "$interval"
done
