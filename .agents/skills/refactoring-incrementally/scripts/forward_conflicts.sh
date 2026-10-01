#!/usr/bin/env bash
# Trial-merge <source-ref> into <dest-ref> without touching the working tree.
# Prints conflicted paths, one per line. Exit: 0 clean, 1 conflicts, 2 error.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <source-ref> <dest-ref>" >&2
  exit 2
fi
src=$1
dest=$2

src_sha=$(git rev-parse --verify --quiet "$src^{commit}") || { echo "unknown ref: $src" >&2; exit 2; }
dest_sha=$(git rev-parse --verify --quiet "$dest^{commit}") || { echo "unknown ref: $dest" >&2; exit 2; }

if git merge-base --is-ancestor "$src_sha" "$dest_sha"; then
  exit 0
fi

# git >= 2.38 can merge in memory; older versions need a throwaway worktree.
if git merge-tree -h 2>&1 | grep -q -- '--write-tree'; then
  set +e
  out=$(git merge-tree --write-tree --name-only --no-messages "$dest_sha" "$src_sha")
  status=$?
  set -e
  case $status in
    0) exit 0 ;;
    1) tail -n +2 <<<"$out" | sed '/^$/d' | sort -u; exit 1 ;;
    *) echo "merge-tree failed" >&2; exit 2 ;;
  esac
fi

tmp=$(mktemp -d "${TMPDIR:-/tmp}/forward-conflicts.XXXXXX")
cleanup() {
  git worktree remove --force "$tmp" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT

git worktree add --quiet --detach "$tmp" "$dest_sha" >/dev/null 2>&1
cd "$tmp"
if git -c submodule.recurse=false merge --no-commit --no-ff --quiet "$src_sha" >/dev/null 2>&1; then
  exit 0
fi
conflicts=$(git diff --name-only --diff-filter=U | sort -u)
if [[ -z $conflicts ]]; then
  echo "merge failed without conflicts" >&2
  exit 2
fi
echo "$conflicts"
exit 1
