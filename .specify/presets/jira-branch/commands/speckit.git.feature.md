---
description: "Validate Jira/JPD ticket reference and create a feature branch"
---

# Create Feature Branch

Create and switch to a new git feature branch for the given specification, enforcing a Jira or JPD ticket reference as the branch name suffix.

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

Construct the branch name as `<short-name>-<ticket-id>` (e.g., `user-auth-infp-460`): the ticket ID is the suffix, and the name must be 244 bytes or fewer.

Create the branch and switch to it with one plain git command, written out, without an environment variable before it, so that permission rules can match it:

```bash
git checkout -b "<short-name>-<ticket-id>"
```

If the branch already exists, do not switch to it and do not create another one: stop and tell the user.

The git extension's branch script is not used: it only takes an exact branch name through the `GIT_BRANCH_NAME` environment variable, which keeps permission rules from matching the command.

## Output

Report, as JSON:

- `BRANCH_NAME`: the branch name (e.g., `user-auth-infp-460`)
- `FEATURE_NUM`: the ticket ID resolved in Step 1 (e.g., `infp-460`)
