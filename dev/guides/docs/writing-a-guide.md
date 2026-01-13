# Writing a Documentation Guide

> Part of: `dev/guides/` | Related: [Documentation Guidelines](../../guidelines/documentation.md), [Markdown Standards](../../guidelines/markdown.md)

Step-by-step guide for writing a how-to guide in the Infrahub documentation.

## When to Write a Guide

Write a guide when you need to:

- Teach users how to perform a specific task
- Provide step-by-step instructions
- Address a particular problem or use case
- Create documentation that can be completed independently by any user

If you're explaining concepts or how something works, write a [topic](../../knowledge/) instead.

## Guide Structure Template

Use this structure as a starting point:

```markdown
---
title: [Task description - 2-5 words]
---

## Introduction
Brief statement of the problem/goal and what the user will achieve.

## Prerequisites
- Required setup or knowledge
- Environment requirements
- Assumed prior knowledge

## Steps

### Step 1: [Action/Goal]
Clear, actionable instructions with:
- Code snippets (YAML, GraphQL, shell commands)
- Screenshots or images for visual guidance
- Tabs for alternative methods (Web UI, GraphQL, Shell/cURL)
- How to verify the step is completed

### Step 2: [Action/Goal]
Continue with same structure...

## Verification
How to check that the solution worked as expected:
- Example outputs
- Screenshots
- Potential failure points and solutions

## Advanced Use Cases (Optional)
For complex guides, include advanced scenarios that build on the main use case:
- More sophisticated configurations
- Edge cases and special situations

## Related Resources
Links to related guides, topics, or reference materials
```

## Step-by-Step Process

### 1. Choose a Clear Title

**Good guide titles:**

- Installing Infrahub with Docker
- Creating a custom schema
- Configuring branch permissions
- Importing data from Git
- Setting up GraphQL authentication

**Bad guide titles:**

- Infrahub Installation (too vague)
- Everything About Schemas (too broad, should be a topic)
- How Branches Work (explanation, not a guide)
- Quick Start (too generic)

### 2. Write the Introduction

- State the problem/goal clearly
- Explain what the user will achieve
- Set expectations about complexity or time required

### 3. List Prerequisites

- Required setup or knowledge
- Environment requirements
- Assumed prior knowledge
- Links to setup guides if needed

### 4. Break Down Steps

Each step should:

- Have a clear action verb in the heading
- Provide actionable instructions
- Include verification after major actions
- Use code examples with proper syntax highlighting
- Include screenshots for UI-based tasks
- Offer alternative methods when applicable (use tabs)

### 5. Add Verification

Include a verification section that shows:

- Example outputs
- Screenshots of expected results
- Potential failure points and solutions

### 6. Link to Related Resources

- Link to related guides for alternative approaches
- Link to topics for background information
- Link to reference docs for API details

## Common Patterns

### Multi-Method Tasks

When a task can be accomplished multiple ways:

1. Show most common method first (usually Web UI)
2. Include programmatic alternatives (GraphQL, Python SDK)
3. Include CLI method when applicable

Use tabs to organize alternative methods. See [Markdown Standards](../../guidelines/markdown.md) for tab syntax.

### Complex Workflows

For multi-step workflows:

1. Break into logical sections with clear headings
2. Include verification after each major section
3. Provide troubleshooting tips for common issues
4. Link to related guides for alternative approaches

### Configuration Tasks

For configuration-heavy tasks:

1. Show complete configuration files
2. Highlight the relevant sections
3. Explain what each configuration does briefly
4. Provide validation commands

## Quality Checklist

Before submitting your guide:

- [ ] Title clearly states what will be accomplished (2-5 words)
- [ ] Introduction explains the goal and context
- [ ] Prerequisites are clearly listed
- [ ] Each step has a clear action verb
- [ ] Steps follow a logical sequence
- [ ] Verification steps are included
- [ ] No words like "easy", "simple", or "just"
- [ ] Links to related topics/references are provided
- [ ] Technical terms are defined on first use
- [ ] Code blocks have language tags (see [Markdown Standards](../../guidelines/markdown.md))
- [ ] Screenshots have descriptive alt text (see [Markdown Standards](../../guidelines/markdown.md))
- [ ] Passes `uv run invoke docs.lint`
- [ ] Builds without errors with `uv run invoke docs.build`

## Writing Style

Follow the guide writing style from [Documentation Guidelines](../../guidelines/documentation.md):

- **Direct and imperative**: Use commands that tell the user what to do
- **Task-focused**: Stay focused on the specific goal without digressing
- **Active voice**: "Create a branch" (not "A branch can be created")
- **Imperative mood**: "Click **New Branch**" (not "You should click New Branch")
- **Second person**: Address the user directly with "you"

## Examples

### Good Guide Writing

```markdown
<!-- ✅ Good -->
Create a new branch by clicking **New Branch** in the sidebar.

<!-- ❌ Bad -->
A branch can be created by clicking on the New Branch button located in the sidebar.
```

```markdown
<!-- ✅ Good -->
Configure the repository URL in your `.infrahub.yml` file.

<!-- ❌ Bad -->
The repository URL configuration is done in the .infrahub.yml file.
```

## Workflow

1. **Choose documentation type** - Confirm this should be a guide (not a topic)
2. **Review this guide** - Understand the structure and patterns
3. **Review general guidelines** - See [Documentation Guidelines](../../guidelines/documentation.md)
4. **Review markdown standards** - See [Markdown Standards](../../guidelines/markdown.md)
5. **Create the .mdx file** in `docs/docs/guides/`
6. **Add to navigation** by editing `sidebars.ts`
7. **Lint before committing**: `uv run invoke docs.lint`
8. **Build to verify**: `uv run invoke docs.build`
9. **Serve for human verification**: `uv run invoke docs.serve`

## See Also

- [Documentation Guidelines](../../guidelines/documentation.md) - General documentation writing guidelines
- [Markdown Standards](../../guidelines/markdown.md) - Markdown formatting standards
- `docs/docs/guides/AGENTS.md` - Agent instructions for writing guides
- [Writing a Topic](writing-a-topic.md) - Step-by-step guide for writing topics
