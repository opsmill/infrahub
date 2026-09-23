#!/usr/bin/env bash
# Exits non-zero, with the fix to apply, when the cubic CLI cannot run a review.
# Prints the cubic binary path on success; the installer puts it in ~/.cubic/bin, which is not
# on PATH until a new login shell.
set -uo pipefail

fail() {
  echo "cubic check failed: $1" >&2
  echo "fix: $2" >&2
  exit 1
}

cubic_bin=$(command -v cubic 2>/dev/null || true)
if [[ -z "$cubic_bin" && -x "${HOME}/.cubic/bin/cubic" ]]; then
  cubic_bin="${HOME}/.cubic/bin/cubic"
fi
[[ -n "$cubic_bin" ]] || fail "the cubic CLI is not installed" \
  "curl -fsSL https://cubic.dev/install | bash, then sign in with: cubic auth login"

"$cubic_bin" --version >/dev/null 2>&1 || fail "$cubic_bin does not run" \
  "reinstall with: curl -fsSL https://cubic.dev/install | bash"

auth=$("$cubic_bin" auth list 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
count=$(printf '%s\n' "$auth" | sed -n 's/.*[^0-9]\([0-9][0-9]*\) credentials*.*/\1/p' | tail -1)
[[ -n "$count" ]] || fail "could not read 'cubic auth list' output" \
  "run '$cubic_bin auth list' and check it lists a cli credential"
[[ "$count" -gt 0 ]] || fail "not signed in to cubic" \
  "run '$cubic_bin auth login' (opens a browser)"
printf '%s\n' "$auth" | grep -qE '(^|[^[:alnum:]_-])cli([^[:alnum:]_-]|$)' || fail \
  "no cubic.dev sign-in; only AI provider credentials are stored" \
  "run '$cubic_bin auth login' (opens a browser)"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not inside a Git working tree" \
  "run from the Infrahub repository"

echo "$cubic_bin"
