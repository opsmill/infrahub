#!/bin/sh
# Starts a code review of a pull request that Claude Code or Codex has just opened.
# Usage: pr-review.sh claude|codex, with the hook payload on standard input.
# The review is opt-in: set PR_REVIEW=on to turn it on.

[ -z "$PR_REVIEW_CHILD" ] || exit 0
[ "$PR_REVIEW" = on ] || exit 0

if ! command -v jq >/dev/null 2>&1; then
    message="The automatic PR review needs jq, which is not installed, so no review was started."
    if [ "$1" = claude ]; then
        printf '{"systemMessage": "%s"}\n' "$message"
    else
        echo "$message" >&2
    fi
    exit 0
fi

payload=$(cat)

# Claude Code records a pull request only when the command created one.
claude_pr_url() {
    printf '%s' "$payload" | jq -r 'select(.tool_response.gitOperation.pr.action == "created") | .tool_response.gitOperation.pr.url // empty'
}

codex_pr_url() {
    case "$payload" in
        *"gh pr create"*) ;;
        *) return 0 ;;
    esac
    printf '%s' "$payload" | jq -r '.tool_response | tostring' | grep -oE 'https://github[.]com/[^/ ]+/[^/ ]+/pull/[0-9]+' | head -1
}

enter_session_dir() {
    cd "$(printf '%s' "$payload" | jq -r '.cwd')" || exit 0
}

notify() {
    if command -v osascript >/dev/null 2>&1; then
        osascript -e "display notification \"$2\" with title \"$1\""
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send "$1" "$2"
    fi
}

start_review_skill() {
    url=$(claude_pr_url)
    [ -n "$url" ] || exit 0
    jq -nc --arg u "$url" '{
        systemMessage: ("Starting a background code review of " + $u + ". Its findings will appear in this session when it finishes."),
        hookSpecificOutput: {
            hookEventName: "PostToolUse",
            additionalContext: ("Pull request " + $u + " was just opened and the user has turned on automatic reviews. Run the reviewing-pull-requests skill with the argument " + $u + " now. The review runs in the background, so tell the user that it is running and that its findings will arrive in this session when it finishes.")
        }
    }'
}

codex_review() {
    url=$(codex_pr_url)
    [ -n "$url" ] || exit 0
    enter_session_dir
    findings="$HOME/.cache/pr-review/$(printf '%s' "$url" | cut -d/ -f4-7 | tr / -).md"
    mkdir -p "${findings%/*}"

    # The ChatGPT desktop app ships the Codex CLI without adding it to the PATH.
    codex=$(command -v codex || echo /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex)
    rules="$(git rev-parse --show-toplevel 2>/dev/null)/REVIEW.md"

    # Codex waits for the hook to exit, so the review runs detached.
    (
        base=$(gh pr view "$url" --json baseRefName -q .baseRefName 2>/dev/null || git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | cut -d/ -f2-)
        git fetch -q origin "$base" 2>/dev/null
        # codex review does not accept instructions together with --base, so the base branch and the rules go in the prompt.
        {
            printf 'Review pull request %s: the commits on the current branch that are not on origin/%s. Report the bugs and risks this change introduces, each with its file and line.\n' "$url" "$base"
            if [ -f "$rules" ]; then
                printf '\nFollow these review rules:\n\n'
                cat "$rules"
            fi
        } | PR_REVIEW_CHILD=1 "$codex" review -c 'sandbox_mode="read-only"' - >"$findings" 2>"${findings%.md}.log"
        notify "Review finished" "Findings saved to $findings"
    ) </dev/null >/dev/null 2>&1 &
}

case "$1" in
    claude) start_review_skill ;;
    codex) codex_review ;;
    *)
        echo "Usage: pr-review.sh claude|codex" >&2
        exit 1
        ;;
esac
