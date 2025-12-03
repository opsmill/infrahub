# New Component Flow

This is a guided flow for creating a new React component. Follow these steps carefully.

**Important**: Read and follow the shared instructions in `_shared.md` for testing options and execution checklist.

## Step 1: Discovery

Ask the user these questions **one at a time**, waiting for each answer before proceeding to the next:

1. **Issue reference**: Is there a GitHub issue number or Jira ticket for this component? (e.g., `#1234` or `IFC-1234`, or skip if none)
2. **Component name**: What should this component be called?
3. **Purpose**: What problem does this component solve? What is its responsibility?
4. **Location**: Where should this component live? (e.g., shared components, feature-specific, etc.)
5. **Props**: What props/inputs should this component accept? Describe the data it needs.
6. **State**: Does this component need to manage internal state? If so, what state?
7. **Interactions**: What user interactions should it handle? (clicks, inputs, etc.)
8. **Testing**: How should this component be tested? (See testing options in `_shared.md`)
9. **Reference**: Are there existing components in the codebase I should reference for patterns or styling?

After gathering all answers, summarize the component design and confirm with the user before proceeding.

## Step 2: Planning

Enter plan mode and create a detailed implementation plan:

- Explore similar components in the codebase for patterns
- Identify shared utilities, hooks, or styles to reuse
- Plan the component structure (props interface, state, handlers)
- Consider accessibility requirements
- Determine what tests are needed based on user's preference
- Present the plan for user approval

## Step 3: Execution

After plan approval, follow the execution checklist in `_shared.md`, plus:

- Create the component file(s)
- Implement props interface/types
- Build the component logic and JSX
- Add styles following project conventions
