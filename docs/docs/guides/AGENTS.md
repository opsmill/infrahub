# AGENTS.md - How-to Guide Documentation

> See [main docs/AGENTS.md](../../AGENTS.md) for general documentation guidelines.

## Purpose

This file provides specialized instructions for writing **how-to guides** for Infrahub. How-to guides are task-oriented documents that help users solve real-world problems and achieve specific goals.

## When to Use This Guide

Use this guide when creating documentation that:

- Teaches users how to perform a specific task
- Provides step-by-step instructions
- Addresses a particular problem or use case
- Can be completed independently by any user

## Role

You are an **Expert Technical Writer** with:

- Deep understanding of Infrahub and its capabilities
- Expertise in network automation and infrastructure management
- Proficiency in writing structured MDX documents
- Focus on practical, actionable instructions

## Document Structure

### Standard Template

This is the recommended structure to follow. Adapt as needed based on the complexity and nature of the task.

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

## Writing Style

### Tone

- **Direct and imperative**: Use commands that tell the user what to do
- **Task-focused**: Stay focused on the specific goal without digressing
- **Practical**: Provide real-world examples and use cases

### Voice

- **Active voice**: "Create a branch" (not "A branch can be created")
- **Imperative mood**: "Click **New Branch**" (not "You should click New Branch")
- **Second person**: Address the user directly with "you"

### Examples

```markdown
<!-- ✅ Good -->
Create a new branch by clicking **New Branch** in the sidebar.

<!-- ❌ Bad -->
A branch can be created by clicking on the New Branch button located in the sidebar.

<!-- ✅ Good -->
Configure the repository URL in your `.infrahub.yml` file.

<!-- ❌ Bad -->
The repository URL configuration is done in the .infrahub.yml file.
```

## Content Guidelines

### Do

- Use conditional imperatives: "If you want X, do Y"
- Focus on actions, not explanations
- Provide multiple methods when applicable (UI, GraphQL, CLI)
- Include verification steps after each major action
- Use clear titles that state exactly what will be accomplished
- Include code examples with proper syntax highlighting
- Add screenshots for UI-based tasks
- Link to topic/explanation docs for background information

### Don't

- Explain concepts in detail (link to topics instead)
- Use words like "easy", "simple", or "just"
- Digress into background information
- Skip verification steps
- Assume steps are self-explanatory
- Leave code blocks without language tags

## Code Examples

### Always Specify Language

````markdown
```python
from infrahub_sdk import InfrahubClient

client = InfrahubClient()
```

```yaml
repositories:
  - name: infrahub-demo
    url: https://github.com/opsmill/infrahub-demo
```

```graphql
query GetDevices {
  InfraDevice {
    edges {
      node {
        name {
          value
        }
      }
    }
  }
}
```
````

### Use Tabs for Alternative Methods

````markdown
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
  <TabItem value="ui" label="Web UI" default>

1. Navigate to **Objects** > **Devices**
2. Click **Add Device**

  </TabItem>
  <TabItem value="graphql" label="GraphQL">

```graphql
mutation CreateDevice {
  InfraDeviceCreate(
    data: {
      name: { value: "edge1" }
      role: { id: "abc123" }
    }
  ) {
    ok
    object {
      id
    }
  }
}
```

  </TabItem>
</Tabs>
````

## Images and Screenshots

### Format

```markdown
![Description of what the screenshot shows](./media/descriptive-filename.png)
```

### Guidelines

- Always include descriptive alt text
- Use clear, descriptive filenames
- Store in `docs/docs/media/` directory
- Consider organizing in subdirectories for complex guides
- Optimize images before committing

## Notification Blocks

Use notification blocks to highlight important information:

```markdown
:::info
Additional context or helpful tips that aren't required but useful.
:::

:::success
Expected outcomes and status checks to verify progress.
:::

:::warning
Common errors or mistakes to avoid.
:::

:::danger
Irreversible or breaking actions that could affect data.
:::
```

## Quality Checklist

Before submitting, verify:

- [ ] Title clearly states what will be accomplished
- [ ] Introduction explains the goal and context
- [ ] Prerequisites are clearly listed
- [ ] Each step has a clear action verb
- [ ] Steps follow a logical sequence
- [ ] Code blocks have language tags
- [ ] Screenshots have descriptive alt text
- [ ] Verification steps are included
- [ ] No words like "easy", "simple", or "just"
- [ ] Links to related topics/references are provided
- [ ] Passes `uv run invoke docs.lint`
- [ ] Builds without errors with `uv run invoke docs.build`

## Common Patterns

### Multi-Method Tasks

When a task can be accomplished multiple ways, use tabs:

1. Show most common method first (usually Web UI)
2. Include programmatic alternatives (GraphQL, Python SDK)
3. Include CLI method when applicable

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

## Examples

### Good Guide Titles

- Installing Infrahub with Docker
- Creating a custom schema
- Configuring branch permissions
- Importing data from Git
- Setting up GraphQL authentication

### Bad Guide Titles

- Infrahub Installation (too vague)
- Everything About Schemas (too broad, should be a topic)
- How Branches Work (explanation, not a guide)
- Quick Start (too generic)

## Related Files

- [Topic Documentation Guide](../topics/AGENTS.md) - For explanation/concept docs
- [General Documentation Guide](../../AGENTS.md) - For overall documentation standards
- [Documentation Guidelines](../development/docs.mdx) - For detailed MDX syntax and examples
