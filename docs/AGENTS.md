# AGENTS.md - Documentation

> See [root AGENTS.md](../AGENTS.md) for project-wide commands and guidelines.

## Overview

Docusaurus documentation site following the [Diataxis framework](https://diataxis.fr/).

## File Structure

- `docs/` – MDX content
  - `guides/` – How-to guides (task-oriented)
  - `topics/` – Explanations (understanding-oriented)
  - `reference/` – API/config reference
  - `tutorials/` – Learning tutorials
  - `media/` – Images and screenshots
- `sidebars.ts` – Navigation configuration

## Commands

```bash
npm run start          # Dev server with hot reload
npm run build          # Production build (checks broken links)
uv run invoke docs.lint # Lint with Vale + markdownlint
```

## Audience

- **Primary:** Automation engineers, network ops, infrastructure teams
- **Assumed:** Git, CI/CD, YAML/JSON, infrastructure-as-code knowledge
- **Not assumed:** Prior Infrahub knowledge

## Writing Style

### Tone

- Professional but approachable
- Concise and direct
- Active voice, imperative mood

```markdown
<!-- ✅ Good -->
Create a branch by clicking **New Branch**.

<!-- ❌ Bad -->
A branch can be created by clicking on the New Branch button.
```

### Code Blocks

Always specify language:

````markdown
```python
from infrahub_sdk import InfrahubClient
```
````

### Images

```markdown
![Alt text describing the image](./media/descriptive-filename.png)
```

## Document Templates (Diataxis)

### How-to Guide Structure

```markdown
---
title: How to [accomplish task]
---

## Introduction
Brief statement of the problem/goal. What the user will achieve.

## Prerequisites
- Required setup or knowledge

## Steps

### Step 1: [Action]
Instructions with code snippets, screenshots, or tabs for alternatives.

### Step 2: [Action]
...

## Verification
How to confirm success. Example outputs.

## Related Resources
Links to related guides or topics.
```

### Topic/Explanation Structure

```markdown
---
title: About [concept]
---

## Introduction
Why this topic matters. Questions this will answer.

## Concepts
Key terms and how they fit the broader system.

## How It Works
Architecture, design decisions, component interactions.

## Related Topics
Links to related concepts and guides.
```

## Quality Checklist

**For Guides:**

- Title states what will be accomplished
- Steps are actionable, not explanatory
- Includes verification steps
- Addresses real-world complexity

**For Topics:**

- Explains "why", not just "what"
- Provides context and background
- Connects to related concepts

## Boundaries

### Always Do

- Run `uv run invoke docs.lint` before committing
- Build docs to check for broken links
- Use sentence case for headings
- Include language tags on code blocks

### Ask First

- New top-level navigation sections
- Docusaurus configuration changes

### Never Do

- Use "simple", "easy", or "just" (minimizes complexity)
- Leave broken links
- Commit large unoptimized images
- Skip alt text for images
