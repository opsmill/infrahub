#!/usr/bin/env bash
# ship-gate-check — Claude Code PreToolUse hook shipped by the opsmill-dev-judging-changes skill.
# Active only when the repo opted in (.claude/quality-gates/enabled); overridable via
# QUALITY_GATES_BYPASS=1. The on-disk `quality-gates` names are kept for compatibility with repos
# that opted in before the gates became standalone skills. Two deterministic gates:
#   (A) Branch discipline: deny `git commit`/`git push` on a protected branch (Bash only).
#   (B) Ship-gate receipt: deny irreversible ship actions unless a commit-bound PASS/DEGRADED
#       receipt exists for HEAD. Ship actions = gh pr create|merge, git push --force*,
#       AGENT_*_COMPLETE marker stamps via `gh pr` (Bash), and MCP PR/MR create|merge tools.
# Detection is LEXICAL and best-effort: it covers the common command shapes, not every possible
# invocation. It is defense-in-depth; the /opsmill-dev-judging-changes skill is the primary control.
# Infrastructure errors fail OPEN; an operational error (no git repo on a detected ship action)
# fails CLOSED.

input=$(cat 2>/dev/null) || exit 0
command -v jq >/dev/null 2>&1 || { echo "[quality-gates] jq not found — gate disabled" >&2; exit 0; }

tool=$(printf '%s' "$input" | jq -r '.tool_name // ""' 2>/dev/null) || exit 0
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null) || exit 0
proj=$(printf '%s' "$input" | jq -r '.cwd // ""' 2>/dev/null) || exit 0
[ -n "$proj" ] || proj="${CLAUDE_PROJECT_DIR:-.}"

# Activation + escape hatch.
[ -f "$proj/.claude/quality-gates/enabled" ] || exit 0
[ "${QUALITY_GATES_BYPASS:-}" = "1" ] && exit 0

emit_deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
emit_allow() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",permissionDecisionReason:$r}}'
  exit 0
}

# ---- Gate A: branch discipline (Bash git only) ----
# Tolerate leading whitespace, command separators, sudo/doas/command/env, and env-assignments.
if [ "$tool" = "Bash" ] && printf '%s' "$cmd" | grep -Eq '(^|[[:space:]]|[;&|(])(([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*|sudo|doas|command|env)[[:space:]]+)*git[[:space:]]+(commit|push)([[:space:]]|$)'; then
  branch=$(git -C "$proj" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "")
  case "$branch" in
    main|master|develop|stable|release/*|release-*)
      emit_deny "quality-gates branch discipline: refusing a commit/push on protected branch '$branch'. Create a feature branch first. Override: QUALITY_GATES_BYPASS=1." ;;
  esac
fi

# ---- Gate B: ship-gate receipt ----
is_ship=0
if [ "$tool" = "Bash" ]; then
  printf '%s' "$cmd" | grep -Eq 'gh[[:space:]]+pr[[:space:]]+(create|merge)' && is_ship=1
  # force-push: a `git push` plus a force-flag token (keeps --force-with-lease gated)
  if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+push' && printf '%s' "$cmd" | grep -Eq '[[:space:]](-f|--force)([[:space:]=]|-with-lease|$)'; then is_ship=1; fi
  # completion-marker stamp: only when written via a `gh pr` command (the real mechanism)
  if printf '%s' "$cmd" | grep -Eq 'gh[[:space:]]+pr' && printf '%s' "$cmd" | grep -Eq 'AGENT_(FIX|TEST)_COMPLETE'; then is_ship=1; fi
elif printf '%s' "$tool" | grep -q '^mcp__'; then
  # MCP PR/MR create|merge (tool naming varies by server; best-effort).
  if printf '%s' "$tool" | grep -Eqi '(pull[_-]?request|merge[_-]?request|[_-]pr([_-]|$)|[_-]mr([_-]|$))' && printf '%s' "$tool" | grep -Eqi '(create|merge|open|submit)'; then
    is_ship=1
  else
    echo "[quality-gates] MCP tool '$tool' not recognized as a ship action — verify coverage if it creates/merges PRs/MRs." >&2
  fi
fi
[ "$is_ship" = 1 ] || exit 0

head=$(git -C "$proj" rev-parse HEAD 2>/dev/null) || head=""
[ -n "$head" ] || emit_deny "quality-gates: cannot determine HEAD; refusing this ship action. Run inside a git repo, or set QUALITY_GATES_BYPASS=1."

receipt="$proj/.claude/quality-gates/receipts/${head}.json"
verdict=""
[ -f "$receipt" ] && verdict=$(jq -r --arg h "$head" 'if (.sha==$h) then (.verdict // "") else "" end' "$receipt" 2>/dev/null)
case "$verdict" in
  PASS) exit 0 ;;
  DEGRADED) emit_allow "quality-gates: shipping under a DEGRADED gate for commit ${head} (R2 fallback — in-context re-read, no independent judge). Verify manually." ;;
esac
emit_deny "quality-gates: no ship-gate receipt for commit ${head}. Run /opsmill-dev-judging-changes with the change's original criteria; on PASS it writes .claude/quality-gates/receipts/${head}.json. Override with QUALITY_GATES_BYPASS=1."
