---
description: "Validate Jira/JPD ticket reference and create a feature branch"
---

# Create Infrahub Feature Branch

Create and switch to a new git feature branch for the given specification, enforcing an Infrahub Jira or JPD ticket reference as the branch name suffix.

## User Input

```text
$ARGUMENTS
```

## Prerequisites

- Verify Git is available by running `git rev-parse --is-inside-work-tree 2>/dev/null`
- If Git is not available, warn the user and skip branch creation

## Step 1: Resolve Ticket Reference

Parse `$ARGUMENTS` for a ticket ID matching either of these formats:

- JPD format: `infp-[0-9]+` (e.g., `infp-460`)
- Jira epic format: `ifc-[0-9]+` (e.g., `ifc-2140`)

If no ticket ID is found in the arguments, prompt the user:

> "Please provide a Jira or JPD reference for this feature (e.g., `infp-460` for a JPD item or `ifc-2140` for a Jira epic):"

Do not proceed until a valid ticket ID is provided. Never invent or skip it.

## Step 2: Generate Short Name

Generate a concise short name (2-4 words) from the feature description:

- Use action-noun format when possible (e.g., `user-auth`, `fix-payment-timeout`)
- Preserve technical terms and acronyms (OAuth2, API, JWT, etc.)
- Examples:
  - "Add user authentication" → `user-auth`
  - "Implement OAuth2 integration for the API" → `oauth2-api-integration`
  - "Fix payment processing timeout bug" → `fix-payment-timeout`

## Step 3: Create Branch

Construct the branch name as `<short-name>-<ticket-id>` (e.g., `user-auth-infp-460`), then pass it as `GIT_BRANCH_NAME` to bypass the script's automatic numbering:

```bash
GIT_BRANCH_NAME="<short-name>-<ticket-id>" .specify/extensions/git/scripts/bash/create-new-feature.sh --json "<feature description>"
```

Example:

```bash
GIT_BRANCH_NAME="user-auth-infp-460" .specify/extensions/git/scripts/bash/create-new-feature.sh --json "Add user authentication"
```

**IMPORTANT**:

- Always construct `GIT_BRANCH_NAME` as `<short-name>-<ticket-id>` — ticket ID is the suffix
- Always include `--json` so output can be parsed reliably
- Run this script exactly once per feature
- For single quotes in args, use escape syntax: `'I'\''m Groot'`

## Output

The script outputs JSON with:

- `BRANCH_NAME`: The branch name (e.g., `user-auth-infp-460`)
- `FEATURE_NUM`: The ticket ID
