# Writing a Documentation Topic

> Part of: `dev/guides/docs/` | Related: `dev/guidelines/documentation.md`, `dev/guidelines/markdown.md`

Step-by-step guide for writing a topic/explanation document in the Infrahub documentation.

## When to Write a Topic

Write a topic when you need to:

- Explain how something works
- Provide background and context
- Clarify concepts and terminology
- Answer "why" questions
- Describe architecture and design decisions

If you're teaching users how to perform a specific task, write a [guide](writing-a-guide.md) instead.

## Topic Structure Template

Use this structure as a starting point:

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

## Step-by-Step Process

### 1. Choose a Clear Title

- Use the topic name, not a sentence
- Examples: "Branches", "Schema validation", "User management and authentication"
- Avoid: "How Branches Work" (too guide-like), "Everything About Schemas" (too broad)

### 2. Write the Introduction

- Brief overview (1-2 sentences) of what the topic covers
- Explain why this topic matters
- Set the context for the rest of the document

### 3. Define Concepts

- Define key terms when first used
- Explain how concepts fit into the broader system
- Use consistent terminology (see Terminology section below)

### 4. Explain How It Works

- Describe the architecture and design
- Explain component interactions
- Provide design rationale
- Discuss trade-offs and alternatives

### 5. Provide Context and Background

- Explain why this approach was chosen
- Describe technical constraints
- Discuss alternative approaches that were considered

### 6. Use Mental Models

- Provide analogies to familiar concepts
- Connect to existing knowledge
- Help readers build understanding through comparison

### 7. Connect to Other Concepts

- Link to related topics
- Explain integration points
- Show dependencies and relationships

## Layered Explanation Approach

When explaining complex concepts, use this layered approach:

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

## Architecture Explanations

When explaining architecture, follow this structure:

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

## Notification Blocks

Use notification blocks appropriately in topics:

- **Info blocks**: For background information that provides additional context
- **Warning blocks**: For common misconceptions or important distinctions

**Note**: Avoid `success` and `danger` blocks in topics - they're more appropriate for guides.

See `dev/guidelines/markdown.md` for notification block syntax.

## Quality Checklist

Before submitting your topic:

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
- [ ] Passes `uv run invoke docs.lint`
- [ ] Builds without errors with `uv run invoke docs.build`

## Writing Style

Follow the topic writing style from `dev/guidelines/documentation.md`:

- **Discursive and reflective**: Invite understanding through explanation
- **Contextual**: Provide background and rationale
- **Analytical**: Explore the "why" behind decisions
- **Present tense**: "Infrahub uses branches to isolate changes"
- **Third person acceptable**: "The schema defines the data model"

## Examples

### Good Topic Writing

```markdown
<!-- ✅ Good -->
Infrahub's branching model is inspired by Git but adapted for infrastructure data.
Unlike Git, which tracks file changes, Infrahub branches track changes to graph
database nodes and relationships. This allows for isolated testing of infrastructure
changes before merging them into production.

<!-- ❌ Bad -->
Create a branch to test changes. Branches are like Git. Use them for testing.
```

```markdown
<!-- ✅ Good -->
The schema validation system ensures data integrity by checking all mutations against
the defined schema before committing them to the database. This prevents invalid data
from entering the system and maintains consistency across branches.

<!-- ❌ Bad -->
To validate schema, run the validation command. Schema validation is important.
```

## Workflow

1. **Choose documentation type** - Confirm this should be a topic (not a guide)
2. **Review this guide** - Understand the structure and patterns
3. **Review general guidelines** - See `dev/guidelines/documentation.md`
4. **Review markdown standards** - See `dev/guidelines/markdown.md`
5. **Create the .mdx file** in `docs/docs/topics/`
6. **Add to navigation** by editing `sidebars.ts`
7. **Lint before committing**: `uv run invoke docs.lint`
8. **Build to verify**: `uv run invoke docs.build`
9. **Serve for human verification**: `uv run invoke docs.serve`

## See Also

- `dev/guidelines/documentation.md` - General documentation writing guidelines
- `dev/guidelines/markdown.md` - Markdown formatting standards
- `dev/guides/docs/writing-a-guide.md` - Guide for writing guides
- `docs/docs/topics/AGENTS.md` - Agent instructions for writing topics

