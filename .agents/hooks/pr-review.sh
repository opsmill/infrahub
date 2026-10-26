#!/bin/sh
# Starts a code review of a pull request that Claude Code or Codex has just opened.
# Usage: pr-review.sh notice|review|codex, with the hook payload on standard input.
# Set PR_REVIEW=off to turn the review off.

[ -z "$PR_REVIEW_CHILD" ] || exit 0
[ "$PR_REVIEW" != off ] || exit 0

if ! command -v jq >/dev/null 2>&1; then
    message="The automatic PR review needs jq, which is not installed, so no review was started."
    if [ "$1" = notice ]; then
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

review_rules() {
    printf '%s/REVIEW.md' "$(git rev-parse --show-toplevel 2>/dev/null)"
}

notify() {
    if command -v osascript >/dev/null 2>&1; then
        osascript -e "display notification \"$2\" with title \"$1\""
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send "$1" "$2"
    fi
}

notice() {
    url=$(claude_pr_url)
    [ -n "$url" ] || exit 0
    jq -nc --arg u "$url" '{
        systemMessage: ("A code review of " + $u + " started in the background. Its findings will appear in this session when it finishes, usually after 10 to 15 minutes. To turn these reviews off, set PR_REVIEW=off in the env block of your Claude Code settings."),
        hookSpecificOutput: {
            hookEventName: "PostToolUse",
            additionalContext: ("A /code-review xhigh review of " + $u + " is now running in the background. The user has not been told about it yet, so the reply mentions that the review is running and that its findings will arrive in this session when it finishes, usually after 10 to 15 minutes, and that setting PR_REVIEW=off in the env block of ~/.claude/settings.json turns these reviews off.")
        }
    }'
}

review() {
    url=$(claude_pr_url)
    [ -n "$url" ] || exit 0
    enter_session_dir
    name="PR review $(printf '%s' "$url" | cut -d/ -f4-7 | sed 's|/pull/|#|')"
    commit=$(gh pr view "$url" --json headRefOid -q .headRefOid 2>/dev/null | cut -c1-7)
    [ -z "$commit" ] || name="$name @ $commit"

    # The local /code-review reads CLAUDE.md files but not REVIEW.md, so the rules go in as an extra CLAUDE.md.
    set --
    dir=
    rules=$(review_rules)
    if [ -f "$rules" ]; then
        dir=$(mktemp -d) && cp "$rules" "$dir/CLAUDE.md" && set -- --add-dir "$dir"
    fi

    # --add-dir takes a list of values, so it comes last.
    out=$(PR_REVIEW_CHILD=1 CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 claude -p "/code-review xhigh $url" -n "$name" --setting-sources user --permission-mode auto "$@" 2>&1)
    [ -z "$dir" ] || rm -rf "$dir"

    # Exit code 2 hands standard error back to the session as the findings.
    printf 'Review of %s:\n%s\n' "$url" "$out" >&2
    exit 2
}

codex_review() {
    url=$(codex_pr_url)
    [ -n "$url" ] || exit 0
    enter_session_dir
    findings="$HOME/.cache/pr-review/$(printf '%s' "$url" | cut -d/ -f4-7 | tr / -).md"
    mkdir -p "${findings%/*}"

    # The ChatGPT desktop app ships the Codex CLI without adding it to the PATH.
    codex=$(command -v codex || echo /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex)
    rules=$(review_rules)

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
    notice) notice ;;
    review) review ;;
    codex) codex_review ;;
    *)
        echo "Usage: pr-review.sh notice|review|codex" >&2
        exit 1
        ;;
esac
