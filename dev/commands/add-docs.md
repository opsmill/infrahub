# Documentation Flow

This is a guided flow for creating or updating documentation. Follow these steps carefully.

**Important**: Read and follow the shared instructions in `_shared.md` for the execution checklist.

## Step 1: Discovery

Ask the user these questions **one at a time**, waiting for each answer before proceeding to the next:

1. **Subject**: What needs to be documented? (component, feature, API, process, etc.)
2. **Type**: What type of documentation is this?
   - Tutorial (learning-oriented, guides through a learning experience)
   - How-to guide (task-oriented, steps to accomplish a specific goal)
   - Explanation/Topic (understanding-oriented, explains concepts)
   - Reference (information-oriented, technical descriptions)
3. **Audience**: Who is the target reader? What do they already know?
4. **Location**: Where should this documentation live? (existing file to update, or new file?)
5. **Scope**: What should be covered? What should be explicitly excluded?
6. **Examples**: Are there specific examples, code snippets, or screenshots needed?

After gathering all answers, summarize the documentation plan and confirm with the user before proceeding.

## Step 2: Planning

Enter plan mode and create a detailed documentation plan:

- Review existing documentation for style and patterns
- Explore the code/feature being documented to ensure accuracy
- Outline the document structure following Diataxis principles
- Identify code examples, diagrams, or screenshots needed
- Consider cross-references to related documentation
- Present the outline for user approval

## Step 3: Execution

After plan approval, follow the execution checklist in `_shared.md`, plus:

- Write the documentation following project conventions
- Include accurate code examples
- Add cross-references and links where helpful
- Run Vale to check style: `vale <filepath>`
- Run markdownlint to check formatting
