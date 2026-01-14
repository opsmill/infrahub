# AGENTS.md - Documentation

> See [root AGENTS.md](../AGENTS.md) for project-wide commands and guidelines.

## Overview

Infrahub documentation is organized using the [Diataxis framework](https://diataxis.fr/), separating documentation into four categories:

- **Tutorials** - Learning-oriented walkthroughs
- **Guides** - Task-oriented how-to documentation
- **Topics** - Understanding-oriented explanations
- **Reference** - Information-oriented specifications

## Before You Start

**Choose the right documentation type:**

| Question | Doc Type | See Guide |
|----------|----------|-----------|
| Teaching users to complete a specific task? | **Guide** | [guides/AGENTS.md](docs/guides/AGENTS.md) |
| Explaining concepts or how something works? | **Topic** | [topics/AGENTS.md](docs/topics/AGENTS.md) |
| Providing reference information? | **Reference** | Auto-generated |
| Walking through a complete learning scenario? | **Tutorial** | Diataxis framework |

## File Structure

- `docs/` – MDX content
  - `guides/` – How-to guides (task-oriented)
    - `AGENTS.md` – **Specialized instructions for writing guides**
  - `topics/` – Explanations (understanding-oriented)
    - `AGENTS.md` – **Specialized instructions for writing topics**
  - `reference/` – API/configuration reference
  - `tutorials/` – Learning tutorials
  - `media/` – Images and screenshots
  - `development/` – Developer documentation
    - `docs.mdx` – Full documentation guide with linting rules
- `sidebars.ts` – Navigation configuration

## Commands

```bash
# Linting & Validation
uv run invoke docs.lint          # Run all linters (Vale + markdownlint)

# Development
uv run invoke docs.build         # Build documentation site
uv run invoke docs.serve         # Serve documentation site

# Format
uv run invoke docs.format        # Auto-format markdown files
```

## Target Audience

- **Primary:** Automation engineers, network operators, infrastructure teams
- **Assumed knowledge:** Git, CI/CD, YAML/JSON, infrastructure-as-code
- **Not assumed:** Prior Infrahub experience

## Writing Guides

For step-by-step instructions on writing documentation:

- `dev/guides/docs/writing-a-guide.md` - How to write how-to guides
- `dev/guides/docs/writing-a-topic.md` - How to write topic/explanation documentation

## Essential Style Guidelines

For detailed markdown formatting rules, see `dev/guidelines/markdown.md`.
For documentation writing guidelines, see `dev/guidelines/documentation.md`.

### Voice and Tone

- **Active voice**: "Create a branch" (not "A branch can be created")
- **Imperative mood** for guides: "Click **New Branch**"
- **Present tense**: "Infrahub uses branches to isolate changes"
- **Professional but approachable**: Avoid "simple", "easy", or "just"

## Documentation Workflow

1. **Choose documentation type** using the table above (if not specified)
2. **Follow specialized guide** (guides/AGENTS.md or topics/AGENTS.md)
3. **Create the .mdx file** in the appropriate directory
4. **Add to navigation** by editing `sidebars.ts` in the appropriate section
5. **Lint before committing**: `uv run invoke docs.lint`
6. **Build to verify**: `uv run invoke docs.build`
7. **Serve for human verification**: `uv run invoke docs.serve`

## Boundaries

### Always Do

- Run `uv run invoke docs.lint` before committing
- Build docs to check for broken links
- Use sentence case for headings
- Include language tags on code blocks
- Choose the appropriate documentation type (guide vs. topic)
- Define technical terms on first use

### Ask First

- New top-level navigation sections
- Docusaurus configuration changes
- Major restructuring of documentation hierarchy

### Never Do

- Use "simple", "easy", or "just" (minimizes complexity)
- Leave broken links
- Commit large unoptimized images
- Skip alt text for images
- Mix guide and topic content in the same document
