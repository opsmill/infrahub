# AGENTS.md - How-to Guide Documentation

> See [main docs/AGENTS.md](../../AGENTS.md) for general documentation guidelines, site structure, and placement decisions.

## Purpose

This file provides specialized instructions for writing **how-to guides** for Infrahub. How-to guides are task-oriented documents that help users accomplish a specific goal.

## Where new guides live in the nav

The `guides/` directory is a **file storage location**, not a nav section. How-to content is surfaced under **Features** capability clusters in the sidebar, grouped with the explanation content for the same feature.

Before creating a guide, use the placement decision checklist in `docs/AGENTS.md` to identify which capability cluster owns it. Then add the file to `sidebars.ts` under that cluster — the file can stay in `guides/` but it will appear under Features in the rendered nav.

**Do not create a new guide and add it to an old `Guides > <category>` sidebar node.** Those nodes are legacy structure being migrated into Features.

## When to write a guide (vs. other content types)

Write a guide when the content:

- Teaches users how to perform a specific task
- Can be reduced to numbered steps with clear action verbs
- Has a defined end state ("you now have X")
- Should be scannable — the reader knows the goal and wants the fastest path

## Role

You are an **Expert Technical Writer** with:

- Deep understanding of Infrahub and its capabilities
- Expertise in network automation and infrastructure management
- Proficiency in writing structured MDX documents
- Focus on practical, actionable instructions

## Quick Reference

For detailed instructions on writing guides, see:

- `dev/guides/docs/writing-a-guide.md` - Step-by-step guide for writing guides
- `dev/guidelines/documentation.md` - General documentation writing guidelines
- `dev/guidelines/markdown.md` - Markdown formatting standards

## Key Principles

### Structure

Follow the guide structure template in `dev/guides/docs/writing-a-guide.md`:

- Introduction with clear goal
- Prerequisites
- Step-by-step instructions
- Verification section
- Related resources

### Writing Style

- **Direct and imperative**: Use commands that tell the user what to do
- **Task-focused**: Stay focused on the specific goal without digressing
- **Active voice**: "Create a branch" (not "A branch can be created")
- **Imperative mood**: "Click **New Branch**" (not "You should click New Branch")
- **Second person**: Address the user directly with "you"

### Content Guidelines

- Use conditional imperatives: "If you want X, do Y"
- Focus on actions, not explanations
- Provide multiple methods when applicable (UI, GraphQL, CLI)
- Include verification steps after each major action
- Use clear titles that state exactly what will be accomplished (2-5 words)
- Link to topic/explanation docs for background information

### Common Patterns

- **Multi-method tasks**: Use tabs to show UI, GraphQL, and CLI methods
- **Complex workflows**: Break into logical sections with verification after each
- **Configuration tasks**: Show complete files, highlight sections, provide validation

See `dev/guides/docs/writing-a-guide.md` for detailed patterns and examples.

## Quality Checklist

Before submitting, verify:

- [ ] Title clearly states what will be accomplished (2-5 words)
- [ ] Introduction explains the goal and context
- [ ] Prerequisites are clearly listed
- [ ] Each step has a clear action verb
- [ ] Steps follow a logical sequence
- [ ] Verification steps are included
- [ ] No words like "easy", "simple", or "just"
- [ ] Links to related topics/references are provided
- [ ] Technical terms are defined on first use
- [ ] Code blocks have language tags (see `dev/guidelines/markdown.md`)
- [ ] Screenshots have descriptive alt text (see `dev/guidelines/markdown.md`)
- [ ] Passes `uv run invoke docs.lint`
- [ ] Builds without errors with `uv run invoke docs.build`

## Related Files

- `dev/guides/docs/writing-a-guide.md` - Step-by-step guide for writing guides
- `dev/guidelines/documentation.md` - General documentation writing guidelines
- `dev/guidelines/markdown.md` - Markdown formatting standards
- [Topic Documentation Guide](../topics/AGENTS.md) - For explanation/concept docs
- [General Documentation Guide](../../AGENTS.md) - For overall documentation standards
- [Documentation Guidelines](../development/docs.mdx) - For detailed MDX syntax and examples
