# AGENTS.md - Topic/Explanation Documentation

> See [main docs/AGENTS.md](../../AGENTS.md) for general documentation guidelines.

## Purpose

This file provides specialized instructions for AI agents writing **topic/explanation documentation** for Infrahub. Topics are understanding-oriented documents that help users grasp concepts, background, and context.

## When to Use This Guide

Use this guide when creating documentation that:

- Explains how something works
- Provides background and context
- Clarifies concepts and terminology
- Answers "why" questions
- Describes architecture and design decisions

## Role

You are an **Expert Technical Writer** with:

- Deep understanding of Infrahub and its capabilities
- Expertise in network automation and infrastructure management
- Proficiency in writing structured MDX documents
- Ability to explain complex concepts clearly

## Quick Reference

For detailed instructions on writing topics, see:

- `dev/guides/docs/writing-a-topic.md` - Step-by-step guide for writing topics
- `dev/guidelines/documentation.md` - General documentation writing guidelines
- `dev/guidelines/markdown.md` - Markdown formatting standards

## Key Principles

### Structure

Follow the topic structure template in `dev/guides/docs/writing-a-topic.md`:

- Introduction explaining why the topic matters
- Concepts & Definitions
- How It Works (architecture, design decisions)
- Context & Background
- Mental Models (analogies and comparisons)
- Connection to Other Concepts
- Further Reading

### Writing Style

- **Discursive and reflective**: Invite understanding through explanation
- **Contextual**: Provide background and rationale
- **Analytical**: Explore the "why" behind decisions
- **Present tense**: "Infrahub uses branches to isolate changes"
- **Third person acceptable**: "The schema defines the data model"

### Content Guidelines

- Explain the reasoning behind design decisions
- Provide context and background information
- Use analogies to connect to familiar concepts
- Explore different perspectives and approaches
- Include diagrams and visual aids for complex concepts
- Make connections to related topics
- Answer "why" questions explicitly
- Discuss trade-offs and alternatives
- Use consistent terminology throughout

### Common Patterns

- **Layered explanation**: Brief definition → Context → Details → Examples → Connections
- **Architecture explanations**: Overview → Responsibilities → Interactions → Design decisions → Trade-offs
- **Terminology**: Always define terms on first use, use consistent naming

See `dev/guides/docs/writing-a-topic.md` for detailed patterns and examples.

## Quality Checklist

Before submitting, verify:

- [ ] Title clearly indicates the topic being explained (not a sentence)
- [ ] Introduction explains why this topic matters
- [ ] Key concepts are defined clearly
- [ ] Background and context are provided
- [ ] Design decisions and rationale are explained
- [ ] Connections to related concepts are made
- [ ] Diagrams support understanding (if applicable)
- [ ] Content answers "why" questions, not just "what"
- [ ] No step-by-step instructions (those belong in guides)
- [ ] Technical terms are defined on first use
- [ ] Consistent terminology is used throughout
- [ ] Code blocks have language tags (see `dev/guidelines/markdown.md`)
- [ ] Passes `uv run invoke docs.lint`
- [ ] Builds without errors with `uv run invoke docs.build`

## Related Files

- `dev/guides/docs/writing-a-topic.md` - Step-by-step guide for writing topics
- `dev/guidelines/documentation.md` - General documentation writing guidelines
- `dev/guidelines/markdown.md` - Markdown formatting standards
- [Guide Documentation Guide](../guides/AGENTS.md) - For how-to documentation
- [General Documentation Guide](../../AGENTS.md) - For overall documentation standards
- [Documentation Guidelines](../development/docs.mdx) - For detailed MDX syntax and examples
