# Markdown Formatting Standards

> Part of: `dev/guidelines/` | Related: [Documentation Guidelines](documentation.md)

Markdown formatting rules enforced by markdownlint and project conventions.

## Basic Formatting

### List Style

- Use `-` for unordered lists (not `*` or `+`)
- Capitalize the first letter of each list item
- If an item is a complete sentence, end with a period
- When listing items with descriptions, prefer colon (:) over dash (-)

```markdown
<!-- ✅ Good -->
- Feature: Explanation of feature
- Another item: With description

<!-- ❌ Bad -->
- Not - this
- Or * this
```

### Spacing

- Add blank line before/after headings
- Add blank line before/after code blocks
- Add blank line before/after lists
- Use two full returns between paragraphs (one empty line)
- No trailing spaces
- No multiple consecutive blank lines

### Headings

- Use sentence case (first word capitalized, rest lowercase)
- No ending punctuation
- Exception: proper nouns remain capitalized
- Every page should have a top-level heading
- Heading tiers must be sequential (don't skip levels)

```markdown
<!-- ✅ Good -->
## Creating a new branch
## Getting started

<!-- ❌ Bad -->
## Creating A New Branch
## Getting Started!
```

### Avoid Over-Capitalization

Unless the term is a named marketing feature, avoid capitalization:

```markdown
<!-- ✅ Good -->
Git repository, API server, user management

<!-- ❌ Bad -->
Git Repository, API Server, User Management
```

## Code Blocks

- Always use fenced code blocks with language identifier
- Use appropriate language tags: `python`, `bash`, `typescript`, `yaml`, `graphql`, `shell`, etc.
- Never leave code blocks without language tags

````markdown
<!-- ✅ Good -->
```python
from infrahub_sdk import InfrahubClient
```

<!-- ❌ Bad -->
```
from infrahub_sdk import InfrahubClient
```
````

## Links

- No bare URLs - use `[text](url)` format
- Use descriptive link text
- Use relative paths for internal documentation links
- All documentation URLs should be relative (not absolute)

```markdown
<!-- ✅ Good -->
[some page](../path/to/file.mdx)

<!-- ❌ Bad -->
[some page](/absolute_path/to/file)
https://example.com/page
```

## Images

- Always include descriptive alt text
- Use clear, descriptive filenames
- Store in appropriate media directories
- Optimize images before committing

```markdown
![Description of what the screenshot shows](./media/descriptive-filename.png)
```

## Language and Style

### Voice and Tone

- **Active voice**: "Create a branch" (not "A branch can be created")
- **Present tense**: "Infrahub uses branches to isolate changes"
- **Professional but approachable**: Avoid "simple", "easy", or "just"
- Use American English for standard text

### Trailing Commas (Oxford Comma)

Use a trailing comma when listing multiple items:

```markdown
<!-- ✅ Good -->
There are devices, organizations, and users.

<!-- ❌ Bad -->
There are devices, organizations and users.
```

### Colons

Avoid extra spaces before a colon:

```markdown
<!-- ✅ Good -->
Feature: Explanation of feature

<!-- ❌ Bad -->
Feature : Explanation of feature
```

## MDX-Specific (Docusaurus)

### Notification Blocks

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

**Usage guidelines:**

- **Info blocks**: Use for additional context or helpful tips
- **Success blocks**: Use in guides to highlight expected outcomes and progress checks
- **Warning blocks**: Use for common errors, mistakes, or important distinctions
- **Danger blocks**: Use in guides for irreversible or breaking actions
- **Topics**: Prefer `info` and `warning` blocks; avoid `success` and `danger` blocks

### Tabs for Alternative Methods

Use tabs when providing multiple ways to accomplish a task:

````markdown
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
  <TabItem value="ui" label="Web UI" default>
    Instructions for UI method
  </TabItem>
  <TabItem value="graphql" label="GraphQL">
    ```graphql
    query { ... }
    ```
  </TabItem>
</Tabs>
````

## General Tips

- Avoid words like "easy", "simple", or "just" to describe tasks
- If a sentence looks too long, simplify it or break into multiple sentences
- Avoid jargon unless you're sure the reader knows the term
- Link between pages and concepts
- Avoid repeating information - link to other pages instead
- Define technical terms on first use

## See Also

- [Documentation Guidelines](documentation.md) - Documentation writing guidelines
- `docs/AGENTS.md` - Documentation-specific guidelines for user-facing docs
- [Git Workflow](git-workflow.md) - Git workflow and commit conventions
