#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
WP_DIR="$REPO_ROOT/dev/spec-kitty/work-packages"
WT_DIR="$REPO_ROOT/dev/spec-kitty/.worktrees"

# Source common functions if available
COMMON_SH="$REPO_ROOT/.specify/scripts/bash/common.sh"
if [[ -f "$COMMON_SH" ]]; then
    source "$COMMON_SH"
fi

usage() {
    cat <<'USAGE'
Usage: manage-workpackages.sh <command> [args...]

Commands:
  list <feature>                        List all WPs with their current lane
  transition <feature> <WP_ID> <lane>   Update WP lane (planned|doing|for_review|done)
  create-worktree <feature> <WP_ID>     Create git worktree for a WP
  cleanup-worktree <feature> <WP_ID>    Remove worktree and optionally delete branch
  status <feature>                      Kanban summary (count per lane)
USAGE
    exit 1
}

get_wp_dir() {
    local feature="$1"
    echo "$WP_DIR/$feature"
}

get_wp_file() {
    local feature="$1"
    local wp_id="$2"
    echo "$(get_wp_dir "$feature")/$wp_id.md"
}

get_lane() {
    local wp_file="$1"
    grep -m1 '^lane:' "$wp_file" | sed 's/^lane: *//'
}

cmd_list() {
    local feature="${1:?Feature name required}"
    local wp_dir
    wp_dir="$(get_wp_dir "$feature")"

    if [[ ! -d "$wp_dir" ]]; then
        echo "No work packages found for feature: $feature"
        exit 1
    fi

    printf "%-8s %-12s %s\n" "ID" "LANE" "TITLE"
    printf "%-8s %-12s %s\n" "------" "----------" "-----"

    for wp_file in "$wp_dir"/WP*.md; do
        [[ -f "$wp_file" ]] || continue
        local wp_id lane title
        wp_id="$(basename "$wp_file" .md)"
        lane="$(get_lane "$wp_file")"
        title="$(grep -m1 '^# Work Package' "$wp_file" | sed 's/^# Work Package WP[0-9]*: //')"
        printf "%-8s %-12s %s\n" "$wp_id" "$lane" "$title"
    done
}

cmd_transition() {
    local feature="${1:?Feature name required}"
    local wp_id="${2:?WP ID required}"
    local new_lane="${3:?New lane required}"
    local wp_file
    wp_file="$(get_wp_file "$feature" "$wp_id")"

    if [[ ! -f "$wp_file" ]]; then
        echo "ERROR: WP file not found: $wp_file"
        exit 1
    fi

    # Validate lane
    case "$new_lane" in
        planned|doing|for_review|done) ;;
        *) echo "ERROR: Invalid lane '$new_lane'. Must be: planned, doing, for_review, done"; exit 1 ;;
    esac

    local old_lane
    old_lane="$(get_lane "$wp_file")"

    # Update lane in frontmatter (portable: works on both macOS and Linux)
    local tmp_file
    tmp_file="$(mktemp)"
    sed "s/^lane: .*/lane: $new_lane/" "$wp_file" > "$tmp_file" && mv "$tmp_file" "$wp_file"

    # Append to activity log (portable: use awk instead of sed -i /a\)
    local timestamp
    timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    tmp_file="$(mktemp)"
    awk -v entry="  - \"$timestamp: $old_lane -> $new_lane\"" '
        /^activity_log:/ { print; print entry; next }
        { print }
    ' "$wp_file" > "$tmp_file" && mv "$tmp_file" "$wp_file"

    echo "Transitioned $wp_id: $old_lane -> $new_lane"
}

cmd_create_worktree() {
    local feature="${1:?Feature name required}"
    local wp_id="${2:?WP ID required}"
    local worktree_path="$WT_DIR/${feature}-${wp_id}"
    local branch_name="kitty/${feature}-${wp_id}"

    if [[ -d "$worktree_path" ]]; then
        echo "Worktree already exists at: $worktree_path"
        exit 1
    fi

    mkdir -p "$WT_DIR"
    git worktree add "$worktree_path" -b "$branch_name"
    echo "Created worktree at: $worktree_path"
    echo "Branch: $branch_name"
}

cmd_cleanup_worktree() {
    local feature="${1:?Feature name required}"
    local wp_id="${2:?WP ID required}"
    local worktree_path="$WT_DIR/${feature}-${wp_id}"
    local branch_name="kitty/${feature}-${wp_id}"

    if [[ -d "$worktree_path" ]]; then
        git worktree remove "$worktree_path" --force
        echo "Removed worktree: $worktree_path"
    else
        echo "No worktree found at: $worktree_path"
    fi

    # Optionally delete branch
    if git rev-parse --verify "$branch_name" &>/dev/null; then
        git branch -d "$branch_name" 2>/dev/null || {
            echo "Branch $branch_name has unmerged changes. Use -D to force delete."
        }
    fi
}

cmd_status() {
    local feature="${1:?Feature name required}"
    local wp_dir
    wp_dir="$(get_wp_dir "$feature")"

    if [[ ! -d "$wp_dir" ]]; then
        echo "No work packages found for feature: $feature"
        exit 1
    fi

    local planned=0 doing=0 for_review=0 done=0 total=0

    for wp_file in "$wp_dir"/WP*.md; do
        [[ -f "$wp_file" ]] || continue
        local lane
        lane="$(get_lane "$wp_file")"
        case "$lane" in
            planned) ((planned++)) ;;
            doing) ((doing++)) ;;
            for_review) ((for_review++)) ;;
            done) ((done++)) ;;
        esac
        ((total++))
    done

    echo "Feature: $feature"
    echo ""
    printf "  PLANNED:    %d\n" "$planned"
    printf "  DOING:      %d\n" "$doing"
    printf "  FOR REVIEW: %d\n" "$for_review"
    printf "  DONE:       %d\n" "$done"
    echo ""
    printf "  TOTAL:      %d\n" "$total"
    if [[ $total -gt 0 ]]; then
        local pct=$(( (done * 100) / total ))
        printf "  PROGRESS:   %d%%\n" "$pct"
    fi
}

# Main dispatch
command="${1:-}"
shift || true

case "$command" in
    list) cmd_list "$@" ;;
    transition) cmd_transition "$@" ;;
    create-worktree) cmd_create_worktree "$@" ;;
    cleanup-worktree) cmd_cleanup_worktree "$@" ;;
    status) cmd_status "$@" ;;
    *) usage ;;
esac
