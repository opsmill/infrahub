# Shared Instructions

These instructions apply to all guided flows.

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
- Summarize what was done when complete
- If a plan file was created, ask the user if they want to remove it

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
```
Title: feat: add breadcrumb navigation for hierarchical schemas [#7549]

Title: fix: resolve sidebar collapse issue [IFC-2847]
```

```
Description:
Adds breadcrumb navigation that displays the full ancestor lineage for objects
and schema hierarchy for hierarchical schemas. Users can search and switch
objects directly from the breadcrumbs.

- Added Breadcrumb component with ancestor traversal
- Integrated with existing navigation context
- Added unit tests for hierarchy resolution
```
