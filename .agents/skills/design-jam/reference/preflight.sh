#!/usr/bin/env bash
# Checks that every skill design-jam invokes is installed and can be started, before a run.
#
# A missing skill does not announce itself: the agent quietly falls back to its own
# judgement and produces something that looks like a design-jam run but skipped the pass
# that mattered. Two minutes here beats discovering it at the review gate.
#
# Usage: bash .agents/skills/design-jam/reference/preflight.sh  (from the repo root)

set -uo pipefail

# "paid|public" means the paid skill is used when installed, the public one otherwise.
REQUIRED=(
  grilling-ideas
  "emil-prototype|prototype"
  emil-design-eng
  break-ui
)

# All four present: phase 4 runs the full review. Otherwise it runs the reduced one.
FULL_REVIEW=(
  emil-ui-polish
  emil-surfaces
  emil-ui-review
  emil-prep-for-prod
)

OPTIONAL=(
  emil-product-thinking
  "emil-animations|animate"
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

# The Skill tool refuses a skill with this flag, so only the user can start it.
user_only() {
  awk 'NR == 1 && /^---$/ { fm = 1; next } fm && /^---$/ { exit } fm' "$1/SKILL.md" |
    grep -qE '^disable-model-invocation:[[:space:]]*true'
}

missing_required=0
missing_review=0
skipped=()
user_run=()
fallbacks=()

check() {
  local entry="$1" label="$2" name path note
  local -a names
  IFS='|' read -r -a names <<<"$entry"
  for name in "${names[@]}"; do
    if path="$(find_skill "$name")"; then
      note="$label"
      if [ "$name" != "${names[0]}" ]; then
        note="$label, public fallback for ${names[0]}"
        fallbacks+=("${names[0]}")
      fi
      if user_only "$path"; then
        note="$note, you type /$name"
        user_run+=("$name")
      fi
      printf '  ok       %-26s %s\n' "$name" "$note"
      return 0
    fi
  done
  printf '  absent   %-26s %s\n' "${entry//|/ or }" "$label"
  return 1
}

echo "design-jam preflight"
echo

for entry in "${REQUIRED[@]}"; do
  check "$entry" "required" || missing_required=$((missing_required + 1))
done

echo
for name in "${FULL_REVIEW[@]}"; do
  check "$name" "full review (paid)" || missing_review=$((missing_review + 1))
done

echo
for entry in "${OPTIONAL[@]}"; do
  check "$entry" "optional" || skipped+=("${entry//|/ or }")
done

echo
if [ "$missing_required" -gt 0 ]; then
  echo "BLOCKED: $missing_required required skill(s) missing."
  echo "  See \"Setup, once per machine\" in .agents/skills/design-jam/SKILL.md."
  echo "  grilling-ideas: ships with this repo (.agents/skills)"
  echo "  prototype, emil-design-eng, break-ui: public, from https://github.com/emilkowalski/skills"
  exit 1
fi

if [ "$missing_review" -gt 0 ] || [ "${#fallbacks[@]}" -gt 0 ]; then
  echo "Skill set: public fallback. Review: reduced (public skills and reference/review-checklist.md)."
  echo "  OpsMill team members: install the paid skills from the internal setup page first,"
  echo "  so every phase runs at full depth."
else
  echo "Skill set: paid. Review: full (paid review skills)."
fi

if [ "${#fallbacks[@]}" -gt 0 ]; then echo "Public fallback for: ${fallbacks[*]}."; fi
if [ "${#skipped[@]}" -gt 0 ]; then echo "Skipped: ${skipped[*]}."; fi
if [ "${#user_run[@]}" -gt 0 ]; then
  echo "User-run: the agent cannot start ${user_run[*]}. When a phase needs one, it asks"
  echo "  you to type the command (for example /${user_run[0]}) and waits."
fi
exit 0
