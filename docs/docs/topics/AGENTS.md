# AGENTS.md - Topic/Explanation Documentation

> See [main docs/AGENTS.md](../../AGENTS.md) for general documentation guidelines.

## Purpose

This file provides specialized instructions for writing **topic/explanation documentation** for Infrahub. Topics are understanding-oriented documents that help users grasp concepts, background, and context.

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

## Document Structure

### Required Elements

```markdown
---
title: [Topic name - not a sentence]
---

## Introduction
Brief overview of what this explanation covers and why it matters.

## Concepts & Definitions
Clear explanations of key terms and how they fit into the broader system.

## How It Works
Architecture, design decisions, and technical details:
- System architecture
- Component interactions
- Design rationale

## Context & Background
Historical context or evolution:
- Why this approach was chosen
- Technical constraints
- Alternative approaches

## Mental Models
Analogies and comparisons to aid understanding:
- How to think about this concept
- Connections to familiar patterns

## Connection to Other Concepts
How this topic relates to other parts of Infrahub:
- Integration points
- Related features
- Dependencies

## Further Reading
Links to related topics, guides, or reference materials
```

## Writing Style

### Tone

- **Discursive and reflective**: Invite understanding through explanation
- **Contextual**: Provide background and rationale
- **Analytical**: Explore the "why" behind decisions
- **Connecting**: Link concepts to existing knowledge

### Voice

- **Active but explanatory**: "Infrahub uses branches to isolate changes"
- **Third person acceptable**: "The schema defines the data model"
- **Present tense**: "A branch represents a parallel version"

### Examples

```markdown
<!-- ✅ Good -->
Infrahub's branching model is inspired by Git but adapted for infrastructure data.
Unlike Git, which tracks file changes, Infrahub branches track changes to graph
database nodes and relationships. This allows for isolated testing of infrastructure
changes before merging them into production.

<!-- ❌ Bad -->
Create a branch to test changes. Branches are like Git. Use them for testing.

<!-- ✅ Good -->
The schema validation system ensures data integrity by checking all mutations against
the defined schema before committing them to the database. This prevents invalid data
from entering the system and maintains consistency across branches.

<!-- ❌ Bad -->
To validate schema, run the validation command. Schema validation is important.
```

## Content Guidelines

### Do

- Explain the reasoning behind design decisions
- Provide context and background information
- Use analogies to connect to familiar concepts
- Explore different perspectives and approaches
- Include diagrams and visual aids for complex concepts
- Make connections to related topics
- Answer "why" questions explicitly
- Discuss trade-offs and alternatives

### Don't

- Provide step-by-step instructions (use guides instead)
- List command references (use reference docs instead)
- Assume prior knowledge of Infrahub-specific concepts
- Use marketing language or hype
- Skip definitions of technical terms
- Focus on "how to" instead of "how it works"

## Explaining Concepts

### Layered Explanation Approach

1. **Brief definition**: Start with a one-sentence explanation
2. **Context**: Explain why this concept matters
3. **Details**: Dive deeper into how it works
4. **Examples**: Provide concrete examples
5. **Connections**: Link to related concepts

### Example

```markdown
## Branches

A branch in Infrahub represents an isolated workspace where you can make and test
infrastructure changes without affecting production.

### Why branches matter

Infrastructure changes are risky. A misconfigured device or incorrect IP assignment
can cause outages. Branches allow you to validate changes in isolation before
applying them to your live infrastructure.

### How branches work

Infrahub's branching model is inspired by Git but adapted for graph data. When you
create a branch, Infrahub creates a copy-on-write view of the database. Changes
made in the branch are tracked separately until you merge them back to the main
branch.

Unlike Git's file-based approach, Infrahub tracks individual nodes and relationships
in the graph database. This granular tracking enables features like:

- Partial merges of specific changes
- Conflict detection at the data level
- Diff views showing exactly what changed

### Comparison to Git

If you're familiar with Git, you can think of Infrahub branches similarly:
- `main` branch is like Git's main/master branch
- Feature branches isolate work in progress
- Merging integrates changes back

However, Infrahub branches differ in important ways:
- They track database entities, not files
- They support concurrent reads from multiple branches
- They enable data-level conflict resolution

### Related concepts

- [Merging and conflicts](./merging.mdx) - How to integrate branch changes
- [Proposed changes](./proposed-changes.mdx) - Workflow for reviewing changes
```

## Terminology and Definitions

### First Use

Always define terms when first used:

```markdown
<!-- ✅ Good -->
A **schema** defines the structure and constraints of your infrastructure data,
similar to a database schema but with additional features for versioning and
validation.

<!-- ❌ Bad -->
Configure the schema to define your data model.
```

### Consistent Naming

Use Infrahub's established terminology consistently:

- Branch (not "workspace" or "environment")
- Schema (not "model definition")
- Proposed change (not "pull request" or "change request")
- Attribute (not "field" or "property")

## Architecture Explanations

### Component Descriptions

When explaining architecture:

1. **Overview**: High-level purpose of the component
2. **Responsibilities**: What this component does
3. **Interactions**: How it communicates with other components
4. **Design decisions**: Why it works this way
5. **Trade-offs**: Benefits and limitations

### Example

```markdown
## GraphQL API Layer

The GraphQL API is Infrahub's primary interface for querying and mutating
infrastructure data. It provides a strongly-typed, flexible alternative to
traditional REST APIs.

### Responsibilities

- Query infrastructure data across branches
- Execute mutations with validation
- Handle real-time subscriptions
- Enforce authentication and authorization

### Design decisions

Infrahub uses GraphQL because:
- **Flexible queries**: Clients request exactly the data they need
- **Strong typing**: Schema provides compile-time validation
- **Branch awareness**: Queries can target specific branches
- **Real-time updates**: Subscriptions enable reactive UIs

### Trade-offs

**Benefits:**
- Reduced over-fetching and under-fetching
- Better developer experience with type safety
- Efficient data loading with DataLoader

**Limitations:**
- More complex than simple REST endpoints
- Requires understanding of GraphQL concepts
- Caching strategies differ from REST
```

## Notification Blocks

Use notification blocks to highlight important information:

```markdown
:::info
Background information that provides additional context.
:::

:::warning
Common misconceptions or important distinctions to understand.
:::
```

**Note**: Avoid `success` and `danger` blocks in topics - they're more appropriate for guides.

## Quality Checklist

Before submitting, verify:

- [ ] Title clearly indicates the topic being explained
- [ ] Introduction explains why this topic matters
- [ ] Key concepts are defined clearly
- [ ] Background and context are provided
- [ ] Design decisions and rationale are explained
- [ ] Connections to related concepts are made
- [ ] Diagrams support understanding (if applicable)
- [ ] Content answers "why" questions, not just "what"
- [ ] No step-by-step instructions (those belong in guides)
- [ ] Technical terms are defined on first use
- [ ] Passes `uv run invoke docs.lint`

## Related Files

- [Guide Documentation Guide](../guides/AGENTS.md) - For how-to documentation
- [General Documentation Guide](../AGENTS.md) - For overall documentation standards
- [Documentation Guidelines](../development/docs.mdx) - For detailed MDX syntax and examples
