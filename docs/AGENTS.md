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
| Teaching users to complete a specific task? | **Guide** | [writing-a-guide.md](../dev/guides/docs/writing-a-guide.md) |
| Explaining concepts or how something works? | **Topic** | [writing-a-topic.md](../dev/guides/docs/writing-a-topic.md) |
| Providing reference information? | **Reference** | Auto-generated |
| Walking through a complete learning scenario? | **Tutorial** | Diataxis framework |

## File Structure

- `docs/` – MDX content
  - `guides/` – How-to guides (task-oriented)
  - `topics/` – Explanations (understanding-oriented)
  - `reference/` – API/configuration reference
  - `tutorials/` – Learning tutorials
  - `media/` – Images and screenshots. Export diagrams (Excalidraw) with an opaque white
    background, not transparent — the docs support a dark theme, where near-black line work on a
    transparent canvas becomes unreadable, and the white card is the established convention here
  - `development/` – Developer documentation
    - `docs.mdx` – Documentation guide with linting rules
    - `style-guide.mdx` – **Writing style and terminology rules**
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
For the complete style guide including terminology, see `docs/development/style-guide.mdx`.

### Voice and Tone

- **Active voice**: "Create a branch" (not "A branch can be created")
- **Imperative mood** for guides: "Click **New Branch**"
- **Present tense**: "Infrahub uses branches to isolate changes"
- **Professional but approachable**: Avoid "simple", "easy", or "just"
- **Literal words**: much of the audience reads English as a second or third language. Avoid figurative phrasing — "carry" (for have), "lives on" (for is stored on), "walk" (for traverse), "reach for" (for use). Say the literal thing.

### Infrahub Terminology

Capitalize these Infrahub-specific terms when referring to the feature:

| Term | Capitalize? | Example |
|------|-------------|---------|
| Generator(s) | Yes | "Infrahub **Generators** convert service models into objects." |
| Transformation(s) | Yes | "**Transformations** convert graph data into artifacts." |
| Profile(s) | Yes | "Create **Profiles** for your devices." |
| Resource Manager | Yes (singular) | "Use **Resource Manager** to allocate IPs." |
| artifact(s) | No | "The **artifact** is stored in object storage." |
| transform (verb) | No | "Use this to **transform** data into vendor formats." |

**Never use "transform" or "transforms" as a noun.** Always use "Transformation" or "Transformations".

**Call a populated instance an "object", not a "node"**, in user-facing text (docs, error messages, UI copy). "Node" stays where it names a schema kind — the counterpart of "Generic" — which is the term the schema docs and the UI already use.

## Documentation Workflow

1. **Choose documentation type** using the table above (if not specified)
2. **Follow specialized guide** (`dev/guides/docs/writing-a-guide.md` or `dev/guides/docs/writing-a-topic.md`)
3. **Create the .mdx file** in the appropriate directory
4. **Add to navigation** by editing `sidebars.ts` in the appropriate section
5. **Lint before committing**: `uv run invoke docs.lint`
6. **Build to verify**: `uv run invoke docs.build`
7. **Serve for human verification**: `uv run invoke docs.serve`

## Restructuring existing docs

When restructuring, merging, or deleting existing pages (on any branch, not only the docs-revamp workflow):

- **Inventory the old content.** Every claim, example, and section from a deleted page gets a home in the new set or an explicit drop decision — including when-to-use guidance and basic CRUD paths, not just the headline topics.
- **Add redirects.** Every deleted or renamed published URL needs an entry in `docs/redirects-pending/` in the same PR.
- **Close every spoke.** In hub+spokes feature docs, each spoke ends with a `## Next` section linking to adjacent spokes.

The `migrate-feature-page` skill documents the full workflow.

## Boundaries

### Always Do

- Run `uv run invoke docs.lint` before committing
- Build docs to check for broken links
- Use sentence case for headings
- Include language tags on code blocks
- Choose the appropriate documentation type (guide vs. topic)
- Define technical terms on first use
- Verify factual claims (attribute kinds, GraphQL fields, defaults, UI button and label text) against the code on the branch the PR targets — docs PRs frequently target a release branch whose features differ from the development branch; this applies doubly before acting on a bot review claim that something "does not exist". For `infrahubctl`/SDK features, the reference is the commit the `python_sdk` submodule pins (`git -C python_sdk show $(git rev-parse HEAD:python_sdk):<path>`), not an SDK branch tip — and never bump the pin just to make docs resolve
- When documenting marketplace items, verify each item actually resolves in the live catalog at <https://marketplace.infrahub.app>; if an item is planned but unpublished, get an explicit decision on release timing before referencing it
- Prefer plain Markdown/MDX over custom React components in doc pages; before adding anything to `docs/src/components/`, check the existing components for reuse, and give a genuinely new component typed props (the docs package typechecks with `tsc`)

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
- Delete or rename a published docs page without adding a redirect entry in `docs/redirects-pending/` (see `docs/redirects-pending/README.md`)
