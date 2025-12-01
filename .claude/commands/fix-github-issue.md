Please analyze and fix the GitHub issue: $ARGUMENTS.

Follow these steps:

1. Use gh issue view to get the issue details
2. Understand the problem described in the issue
3. Search the codebase for relevant files
4. Identify, analyze and describe the root cause of the issue
5. Write a test that confirms the root cause of the issue
6. Come up with an implementation plan to solve the issue and ask for my review
7. Implement the necessary changes to fix the issue
8. Write and run tests to verify the fix
9. Ensure code passes linting and type checking
10. Create a short user-facing changelog entry using towncrier, describing the fixed issue. Reference the GitHub issue in the changelog. Do not focus on the technical aspects of the implemented solution.
11.Create a descriptive commit message, do not mention CLAUDE in the commit message or as co-author

Remember to use the GitHub CLI (gh) for all GitHub-related tasks.
