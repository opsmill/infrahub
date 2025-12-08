# Shared Instructions

These instructions apply to all guided flows.

## Issue/Ticket Reference

During discovery, ask the user:

> **Issue reference**: Is there a GitHub issue number or Jira ticket associated with this work? (e.g., `#1234` for GitHub, `IFC-1234` for Jira, or leave blank if none)

Store this reference to use in:

- Changelog filename (e.g., `+1234.fixed.md` or `+IFC-1234.added.md`)
- PR title (e.g., `fix: resolve bug [#1234]` or `feat: add feature [IFC-1234]`)

## Testing Options

When asking about testing, present these options:

- **Unit test**: Test individual functions/hooks in isolation
- **Component test**: Test component behavior with mock data using testing-library
- **E2E test**: Test full user flows in a real browser with Playwright
- **No tests needed**: Explain why testing isn't required for this change

## Execution Checklist

At the end of every guided flow execution:

- Use the todo list to track all tasks
- Mark tasks complete as you finish them
- Validate changes work as expected
- Add tests if applicable based on user's testing preference
- Suggest creating a changelog fragment (see below)
- Summarize what was done when complete
- If a plan file was created, ask the user if they want to remove it

## Changelog Fragment

After completing a task, suggest creating a changelog fragment file under `/changelog/`.

**File naming pattern**: `+<issue reference | custom name>.<added | fixed>.md`

- If an issue reference was provided, use it (without `#` prefix for GitHub issues)
- Otherwise, use a descriptive custom name
- Use `added` for new features or enhancements
- Use `fixed` for bug fixes

**Examples**:

- `+1234.added.md` - GitHub issue #1234
- `+IFC-1234.fixed.md` - Jira ticket IFC-1234
- `+breadcrumb.added.md` - custom name (no issue reference)
- `+sidebar-collapse.fixed.md` - custom name with fixed type

**Content**: Write a brief, user-facing description of the change. Keep it concise and focus on what was added or fixed from the user's perspective.

## Pull Request

After completing a task, suggest a PR title and description for the user.

**Branch naming pattern**: `<initials>-<short-description>`

**PR title pattern**: `<type>: <short description> [<issue reference>]`

The issue reference is optional and can be:

- GitHub issue number: `#1234`
- Jira ticket: `IFC-1234`

Types:

- `feat` - new feature or enhancement
- `fix` - bug fix
- `docs` - documentation changes
- `refactor` - code refactoring without behavior changes
- `test` - adding or updating tests
- `chore` - maintenance tasks, dependencies, tooling

**PR description**: Provide a brief summary with:

- What was changed and why
- Any notable implementation details
- Testing performed

**Examples**:

```text
Title: feat: add breadcrumb navigation for hierarchical schemas [#7549]

Title: fix: resolve sidebar collapse issue [IFC-2847]
```

```text
Description:
Adds breadcrumb navigation that displays the full ancestor lineage for objects
and schema hierarchy for hierarchical schemas. Users can search and switch
objects directly from the breadcrumbs.

- Added Breadcrumb component with ancestor traversal
- Integrated with existing navigation context
- Added unit tests for hierarchy resolution
```
