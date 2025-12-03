# Guided Task Flow

This is a guided task creation flow. Follow these steps carefully.

## Step 1: Discovery

Ask the user these questions **one at a time**, waiting for each answer before proceeding to the next:

1. **Goal**: What are you trying to accomplish? Describe the feature, fix, or change you need.
2. **Context**: What files or areas of the codebase are involved? (If unsure, I can help explore)
3. **Requirements**: Are there any specific constraints, patterns, or requirements to follow?
4. **Success criteria**: What does success look like? How will we know this is complete?
5. **Testing**: How should this change be tested?
   - **Unit test**: Test individual functions/hooks in isolation
   - **Component test**: Test component behavior with mock data using testing-library
   - **E2E test**: Test full user flows in a real browser with Playwright
   - **No tests needed**: Explain why testing isn't required for this change
6. **Additional context**: Is there anything else I should know? (existing bugs, related features, deadlines, etc.)

After gathering all answers, summarize what you understood and confirm with the user before proceeding.

## Step 2: Planning

Enter plan mode and create a detailed implementation plan based on the answers:

- Explore the relevant codebase areas
- Identify existing patterns to follow
- Break down the work into clear, actionable steps
- Note any potential risks or decision points
- Present the plan for user approval

## Step 3: Execution

After plan approval:

- Use the todo list to track all tasks
- Implement the solution step by step
- Mark tasks complete as you finish them
- Validate changes work as expected
- Summarize what was done when complete
- If a plan file was created, ask the user if they want to remove it
