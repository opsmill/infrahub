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
- Suggest creating a changelog fragment (see below)
- Summarize what was done when complete
- If a plan file was created, ask the user if they want to remove it

## Changelog Fragment

After completing a task, suggest creating a changelog fragment file under `/changelog/`.

**File naming pattern**: `+<pull request number | custom name>.<added | fixed>.md`

- Use `added` for new features or enhancements
- Use `fixed` for bug fixes

**Examples**:
- `+7549.added.md` - PR number with added type
- `+breadcrumb.added.md` - custom name with added type
- `+sidebar-collapse.fixed.md` - custom name with fixed type

**Content**: Write a brief, user-facing description of the change. Keep it concise and focus on what was added or fixed from the user's perspective.
