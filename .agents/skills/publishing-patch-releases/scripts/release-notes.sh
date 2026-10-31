#!/usr/bin/env bash
# Usage: release-notes.sh <version> [<git-ref>]
#
# Prints the CHANGELOG.md section of <version> at <git-ref> (origin/stable by default), from its
# "## [Infrahub - v<version>]" heading up to the heading of the previous release. Run it inside an
# opsmill/infrahub checkout. Exits 1 when CHANGELOG.md has no section for <version>.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 <version> [<git-ref>]" >&2
  exit 64
fi

version=$1
ref=${2:-origin/stable}

git show "${ref}:CHANGELOG.md" |
  awk -v heading="## [Infrahub - v${version}]" '
    done { next }
    index($0, heading) == 1 { found = 1; print; next }
    found && /^## \[Infrahub - v/ { done = 1; next }
    found { print }
    END { if (!found) exit 1 }
  ' |
  sed -e :a -e '/^\n*$/{$d;N;ba' -e '}'
