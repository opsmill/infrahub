# Bug Fix Flow

This is a guided flow for debugging and fixing issues. Follow these steps carefully.

## Step 1: Discovery

Ask the user these questions **one at a time**, waiting for each answer before proceeding to the next:

1. **Symptom**: What is the bug? Describe what is happening that shouldn't be.
2. **Expected behavior**: What should happen instead?
3. **Reproduction**: How can this bug be reproduced? What are the steps?
4. **Location**: Do you know where in the codebase this might be occurring? (files, components, etc.)
5. **Frequency**: Does this happen every time, or intermittently?
6. **Recent changes**: Were there any recent changes that might have caused this?
7. **Error messages**: Are there any error messages in the console, logs, or UI?
8. **Testing**: How should the fix be tested to prevent regression?
   - **Unit test**: Test the fixed function/hook in isolation
   - **Component test**: Test the fixed component behavior with mock data using testing-library
   - **E2E test**: Test the fix within the full user flow using Playwright
   - **No tests needed**: Explain why testing isn't required for this fix

After gathering all answers, summarize your understanding of the bug and confirm with the user before proceeding.

## Step 2: Investigation & Planning

Enter plan mode to investigate and plan the fix:

- Explore the relevant code areas
- Trace the data/logic flow to understand the root cause
- Identify the actual bug (not just the symptom)
- Consider edge cases and related areas that might be affected
- Plan the fix with minimal changes to avoid regressions
- Determine if tests should be added to prevent recurrence
- Present findings and proposed fix for user approval

## Step 3: Execution

After plan approval:

- Use the todo list to track all tasks
- Implement the fix
- Verify the fix resolves the issue
- Check for regressions in related functionality
- Add tests if applicable
- Summarize what was fixed and how when complete
