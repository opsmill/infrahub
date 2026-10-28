#!/usr/bin/env bash
# Checks that every skill design-jam invokes is actually installed, before a run starts.
#
# A missing skill does not announce itself: the agent quietly falls back to its own
# judgement and produces something that looks like a design-jam run but skipped the pass
# that mattered. Two minutes here beats discovering it at the review gate.
#
# Usage: bash .agents/skills/design-jam/reference/preflight.sh  (from the repo root)

set -uo pipefail

REQUIRED=(
  emil-product-thinking
  grilling-ideas
  emil-prototype
  emil-design-eng
  emil-ui-polish
  emil-surfaces
  emil-ui-review
  emil-prep-for-prod
)

OPTIONAL=(
  emil-animations
  emil-mobile-native
  emil-get-creative
  emil-design-foundations
)

REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

find_skill() {
  local name="$1" root
  for root in "$HOME/.claude/skills" "$REPO/.claude/skills" "$REPO/.agents/skills"; do
    [ -f "$root/$name/SKILL.md" ] && { printf '%s\n' "$root/$name"; return 0; }
  done
  # Plugins nest skills a few levels down; take the first match.
  local hit
  hit="$(find "$HOME/.claude/plugins" -maxdepth 6 -type f -path "*/$name/SKILL.md" 2>/dev/null | head -1)"
  [ -n "$hit" ] && { dirname "$hit"; return 0; }
  return 1
}

missing_required=0
missing_optional=()

echo "design-jam preflight"
echo

for name in "${REQUIRED[@]}"; do
  if path="$(find_skill "$name")"; then
    printf '  ok       %-26s %s\n' "$name" "$path"
  else
    printf '  MISSING  %-26s required\n' "$name"
    missing_required=$((missing_required + 1))
  fi
done

echo
for name in "${OPTIONAL[@]}"; do
  if find_skill "$name" >/dev/null; then
    printf '  ok       %-26s conditional\n' "$name"
  else
    printf '  absent   %-26s conditional\n' "$name"
    missing_optional+=("$name")
  fi
done

echo
if [ "$missing_required" -gt 0 ]; then
  echo "BLOCKED: $missing_required required skill(s) missing."
  echo "  See \"Setup, once per machine\" in .agents/skills/design-jam/SKILL.md."
  echo "  emil-design-eng: public, from https://github.com/emilkowalski/skills"
  echo "  other emil-*:    paid, from https://aiforui.dev/learn/skills; ask @pa-lem for the token"
  echo "                   and never commit it"
  echo "  grilling-ideas:  ships with this repo (.agents/skills) or the opsmill-dev plugin"
  exit 1
fi

if [ "${#missing_optional[@]}" -gt 0 ]; then
  echo "OK with gaps: ${missing_optional[*]} unavailable — those passes will be skipped and said so."
  exit 0
fi

echo "OK: every skill available."
