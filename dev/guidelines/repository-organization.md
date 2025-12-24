# Repository Organization

> Part of: `dev/guidelines/` | Related: `dev/adr/0001-context-nuggets-pattern.md`, `dev/README.md`

Comprehensive guidelines for organizing content in the `dev/` directory using the Context Nuggets pattern. This structure enables both humans and AI agents to find what they need, when they need it.

## Core Principles

### Context Nuggets, Not Dumps

- **Small, focused files**: Target 200-400 lines per file, maximum 500 lines
- **One concept per file**: Each file should cover a single, focused topic
- **Link between files**: Cross-reference rather than duplicating content
- **Task-scoped loading**: Load what's needed for this task, not everything

### AGENTS.md as a Map

- **Lightweight routing**: Root `AGENTS.md` should be ~2-3KB with glossary and pointers
- **Not a knowledge dump**: Detailed information lives in `dev/` directory
- **Quick orientation**: Helps agents and humans understand project structure at a glance

### Treat Docs Like Code

- **Version control**: All documentation is versioned and reviewed
- **PRs and reviews**: Documentation changes go through same process as code
- **Clear ownership**: Each file has a clear purpose and can be owned by teams/individuals
- **Active maintenance**: Fix broken links, update outdated content, mark deprecated docs

## Directory Structure

Each directory in `dev/` serves a specific purpose and follows a content lifecycle. The structure answers different questions for different audiences.

### explorations/

**Purpose**: "What are we thinking about?"

**Content Lifecycle**: Rough, temporary. Documents here are early-stage ideas that may or may not graduate to specs.

**Primary Target**: Human

**File Size Guidelines**: 100-300 lines

**When to Use**:

- Quick notes and spikes
- "What if we tried X?" explorations
- Early thinking before approval
- Low ceremony, high velocity

**Example Files**:

- `caching-strategies.md`
- `graphql-subscriptions.md`
- `permission-model-ideas.md`

**Subdirectories**: None typically. Keep flat for easy discovery.

### specs/

**Purpose**: "What are we building?"

**Content Lifecycle**: Approved plans. Living during development, then archived or moved to knowledge/guidelines.

**Primary Target**: Human

**File Size Guidelines**: 200-500 lines

**When to Use**:

- Approved technical designs
- Feature specifications with clear scope
- Implementation plans
- Documents that guide development work

**Example Files**:

- `2024-01-proposed-changes-api.md`
- `2024-03-webhook-notifications.md`

**Subdirectories**: None typically. Use date prefixes or feature names for organization.

**Graduation**: After implementation, specs can be:

- Archived (kept for historical reference)
- Moved to `knowledge/` (if describing how something works)
- Moved to `guidelines/` (if describing how to use something)

### guidelines/

**Purpose**: "What rules should I follow?"

**Content Lifecycle**: Stable, evolving. Prescriptive rules that guide how code should be written.

**Primary Target**: AI (primary), Human (secondary)

**File Size Guidelines**: 100-400 lines

**When to Use**:

- Coding standards and conventions
- Style guides
- Best practices
- Prescriptive rules ("do this, not that")

**Example Files**:

- `git-workflow.md` - Git commit conventions
- `markdown.md` - Markdown formatting standards
- `documentation.md` - Documentation writing guidelines
- `changelog.md` - Changelog entry format

**Subdirectories**: Use domain-based organization when needed:

- `backend/` - Backend-specific standards (e.g., `python.md`)
- `frontend/` - Frontend-specific standards (e.g., `typescript.md`)

**When to Create Subdirectories**:

- When you have multiple files for the same domain (3+ files)
- When standards differ significantly between domains
- When you want to group related guidelines together

**Naming**: Use descriptive, kebab-case names that clearly indicate the topic.

### knowledge/

**Purpose**: "How does this work?"

**Content Lifecycle**: Stable reference. Descriptive documentation explaining how the system works.

**Primary Target**: AI (primary), Human (secondary)

**File Size Guidelines**: 200-400 lines

**When to Use**:

- Architecture explanations
- System design documentation
- How components interact
- Data models and schemas
- Deployment processes
- Reference material (not step-by-step instructions)

**Example Files**:

- `architecture.md` - System overview
- `deployment.md` - How we deploy
- `data-model.md` - Database schema

**Subdirectories**: Use domain-based organization:

- `backend/` - Backend architecture (e.g., `data-model.md`, `query-engine.md`)
- `frontend/` - Frontend architecture (e.g., `state-management.md`, `data-fetching.md`)

**When to Create Subdirectories**:

- When you have multiple knowledge files for the same domain
- When architecture differs significantly between domains
- When you want to group related knowledge together

**Key Distinction**: Knowledge is descriptive ("how it works"), not prescriptive ("how to do it"). For step-by-step instructions, use `guides/`.

### guides/

**Purpose**: "How do I do X?"

**Content Lifecycle**: Stable, updated. Step-by-step procedures for specific tasks.

**Primary Target**: AI (primary), Human (secondary)

**File Size Guidelines**: 200-400 lines

**When to Use**:

- Step-by-step procedures
- Task-specific instructions
- "How to accomplish X" documentation
- Practical, actionable content

**Example Files**:

- `add-graphql-endpoint.md`
- `create-new-node-type.md`
- `write-a-migration.md`
- `debug-query-performance.md`

**Subdirectories**: Use category-based or domain-based organization:

- `docs/` - Documentation-specific guides (e.g., `writing-a-guide.md`, `writing-a-topic.md`)
- `frontend/` - Frontend-specific guides (e.g., `writing-component-tests.md`, `writing-unit-tests.md`)

**When to Create Subdirectories**:

- When you have multiple guides for the same category/domain (3+ files)
- When guides are specific to a particular technology or domain
- When you want to group related guides together

**Naming**: Use action-oriented, kebab-case names (e.g., `writing-a-guide.md`, not `guide-writing.md`).

### adr/

**Purpose**: "Why was this decided?"

**Content Lifecycle**: Permanent record. Architecture Decision Records document why decisions were made.

**Primary Target**: Human

**File Size Guidelines**: 200-500 lines

**When to Use**:

- Significant architectural decisions
- Technology choices
- Design pattern selections
- Trade-off documentation

**Structure**:

- `README.md` - Index of all ADRs
- `template.md` - Template for creating new ADRs
- `NNNN-short-title.md` - Individual ADRs with sequential numbering

**Example Files**:

- `0001-context-nuggets-pattern.md`
- `0002-use-neo4j.md`
- `0003-graphql-over-rest.md`

**Subdirectories**: None. Keep flat with sequential numbering.

**Naming**: Use format `NNNN-short-title.md` where NNNN is a zero-padded 4-digit number.

### commands/

**Purpose**: "Run this for me"

**Content Lifecycle**: Stable. Reusable agent commands that can be executed by AI agents.

**Primary Target**: AI

**File Size Guidelines**: 50-200 lines

**When to Use**:

- Reusable workflows for AI agents
- Standardized procedures
- Command templates
- Agent-executable instructions

**Example Files**:

- `_shared.md` - Shared instructions for all flows
- `new-component.md` - React component creation flow
- `fix-bug.md` - Bug fixing flow
- `add-docs.md` - Documentation creation flow

**Subdirectories**: None. Keep flat for easy discovery by agents.

**Tool Compatibility**: This is the canonical source. Tool-specific directories symlink here:

- `.claude/commands` → `dev/commands`
- `.cursor/commands` → `dev/commands`

**Naming**: Use descriptive, kebab-case names. Prefix shared files with underscore (e.g., `_shared.md`).

### prompts/

**Purpose**: "Help me think about X"

**Content Lifecycle**: Stable. Reusable prompt templates for common thinking tasks.

**Primary Target**: Human

**File Size Guidelines**: 100-300 lines

**When to Use**:

- Thinking frameworks
- Analysis templates
- Problem-solving patterns
- Reusable prompt structures

**Example Files**:

- `bug-analysis.md` - Framework for analyzing bugs
- `design-review.md` - Template for reviewing designs
- `performance-investigation.md` - Pattern for performance analysis

**Subdirectories**: None typically. Keep flat for easy discovery.

**Naming**: Use descriptive, kebab-case names that indicate the thinking task.

### skills/

**Purpose**: "Domain-specific expertise for AI agents"

**Content Lifecycle**: Stable. Specialized knowledge for specific tools, languages, or domains.

**Primary Target**: AI

**File Size Guidelines**: 200-500 lines for SKILL.md, 100-300 lines for reference files

**When to Use**:

- Domain-specific guidance that doesn't fit guidelines or knowledge
- Tool-specific best practices
- Language or framework-specific patterns
- Specialized knowledge for AI agents working with specific technologies

**Structure**: Each skill is a directory:

```text
skills/
└── {skill-name}/
    ├── SKILL.md          # Main skill documentation
    └── references/       # Optional: Supporting reference materials
        ├── file1.md
        └── file2.md
```

**Example**:

```text
skills/
└── neo4j-cypher-guide/
    ├── SKILL.md
    └── references/
        ├── deprecated-syntax.md
        ├── subqueries.md
        └── qpp.md
```

**When to Create**:

- When you need specialized guidance for a specific tool or domain
- When patterns are tool-specific and don't belong in general guidelines
- When you want to provide comprehensive reference material for AI agents
- When the knowledge is highly specialized and benefits from its own structure

**SKILL.md Format**: Should include:

- Quick compatibility checks or common pitfalls
- Core principles
- Pattern selection guides
- Common transformations
- When to load reference documentation
- Error resolution patterns
- Performance tips

**References Subdirectory**: Use when you need to break down the skill into multiple reference documents. Each reference should cover a focused topic.

**Naming**: Use descriptive, kebab-case names for skill directories. The main file must be `SKILL.md`.

## Document Lifecycle

Documents evolve through a lifecycle from rough ideas to stable reference:

```text
explorations/ → specs/ → knowledge/ or guidelines/
   (rough)     (approved)      (stable)
```

### Lifecycle Stages

1. **explorations/**: Quick notes, spikes, early thinking. Low ceremony, high velocity. Not everything here will graduate—that's fine.

2. **specs/**: Approved designs with clear scope. Living during development, then archived or moved to stable reference.

3. **knowledge/ or guidelines/**: Stable reference after implementation. Knowledge describes how things work; guidelines prescribe how to use them.

### Moving Documents

**When to move from explorations to specs**:

- Idea has been approved for implementation
- Clear scope and requirements defined
- Ready to guide development work

**When to move from specs to knowledge/guidelines**:

- Implementation is complete
- Document describes how something works (→ knowledge/)
- Document prescribes how to use something (→ guidelines/)

**How to mark deprecated content**:

- Add a note at the top: `> **Deprecated**: See [new-location](path/to/new-file.md) for current information.`
- Don't delete immediately—update with pointers to replacements
- Remove after a grace period (e.g., 3-6 months) if links are updated

### Link Maintenance

- Use relative paths for internal links
- Review links when moving or renaming files
- Fix broken links as you encounter them
- Include link checking in PR reviews

## File Organization Rules

### File Size

- **Target**: 200-400 lines per file
- **Maximum**: 500 lines before splitting
- **Minimum**: No strict minimum, but files under 50 lines might be better merged

**When to split a file**:

- File exceeds 500 lines
- File covers multiple distinct concepts
- Different sections have different audiences
- File is difficult to navigate

**How to split**:

- Extract logical sections into separate files
- Update original file with links to new files
- Maintain cross-references between related files

### Naming Conventions

- **Format**: kebab-case (e.g., `writing-a-guide.md`, not `writing_a_guide.md` or `WritingAGuide.md`)
- **Descriptive**: Names should clearly indicate the file's content
- **Action-oriented for guides**: Use verbs (e.g., `writing-a-guide.md`, not `guide-writing.md`)
- **Consistent**: Follow established patterns within each directory

### One Concept Per File

Each file should cover a single, focused topic. If you find yourself writing "and also..." frequently, consider splitting the file.

**Good examples**:

- `python.md` - Python coding standards
- `typescript.md` - TypeScript coding standards
- `git-workflow.md` - Git workflow and commits

**Bad examples**:

- `backend-standards.md` - Too broad (should be split into python.md, testing.md, etc.)
- `everything-about-schemas.md` - Too broad (should be split by topic)

### Cross-References

- **Use relative paths**: `../knowledge/architecture.md` not absolute paths
- **Link actively**: Don't duplicate content, link to it
- **Maintain links**: Fix broken links when you encounter them
- **Use descriptive link text**: `[Python coding standards](backend/python.md)` not `[here](backend/python.md)`

## Subdirectory Patterns

### When to Create Subdirectories

Create subdirectories when:

- You have 3+ files for the same domain/category
- Standards or patterns differ significantly between domains
- You want to group related content together
- The directory is becoming difficult to navigate

### Domain-Based Organization

Use for technology or domain-specific content:

**Examples**:

- `guidelines/backend/` - Backend-specific standards
- `guidelines/frontend/` - Frontend-specific standards
- `knowledge/backend/` - Backend architecture
- `knowledge/frontend/` - Frontend architecture

**When to use**:

- Clear separation between technologies (backend vs frontend)
- Different standards or patterns for different domains
- Team ownership aligns with domains

### Category-Based Organization

Use for grouping related content by category:

**Examples**:

- `guides/docs/` - Documentation-specific guides
- `guides/frontend/` - Frontend-specific guides

**When to use**:

- Content is related by category rather than domain
- You want to group similar types of guides together
- Category has clear boundaries

### Reference-Based Organization

Use for supporting materials within a larger structure:

**Examples**:

- `skills/neo4j-cypher-guide/references/` - Supporting reference materials for the skill

**When to use**:

- You have a main document with supporting references
- References are only relevant in context of the main document
- Breaking into references improves navigation

## Tool Compatibility with Claude Code

Maintain a single source of truth with symlinks for tool compatibility, since most tools are able to read the Claude code structure, we'll focus on having simlinks for Claude Code only.

### Symlink Strategy

```bash
# Command directories
.claude/commands → ../dev/commands
.claude/skills → ../dev/skills
```

### Why Symlinks

- **Single source of truth**: Content lives in one place
- **No duplication**: Changes propagate automatically
- **Easy maintenance**: Update once, all tools benefit

### Setting Up Symlinks

```bash
# Remove old directories if they exist
rm -rf .claude/commands .claude/skills

# Create tool directories
mkdir -p .claude 

# Create symlinks to canonical source
ln -s ../dev/commands .claude/commands

```

## Best Practices

### For Authors

1. **Start small**: Don't create structure until you need it
2. **Follow the lifecycle**: Move documents as they mature
3. **Link, don't duplicate**: Cross-reference rather than copying
4. **Keep files focused**: One concept per file
5. **Use descriptive names**: Make it clear what the file contains
6. **Update links**: Fix broken links when you encounter them

### For Reviewers

1. **Check file size**: Flag files over 500 lines for splitting
2. **Verify links**: Ensure cross-references are correct
3. **Check location**: Ensure file is in the right directory
4. **Review lifecycle**: Ensure document is at appropriate stage
5. **Validate structure**: Ensure subdirectories are justified

### For AI Agents

1. **Load task-scoped context**: Don't load everything, load what's needed
2. **Follow the map**: Use `AGENTS.md` to find relevant documentation
3. **Respect the structure**: Create files in appropriate directories
4. **Maintain links**: Update cross-references when creating new files
5. **Check file size**: Split files that exceed 500 lines

## Examples

### Good Organization

```text
dev/
├── guidelines/
│   ├── git-workflow.md          # Shared guideline
│   ├── markdown.md              # Shared guideline
│   ├── backend/
│   │   └── python.md            # Domain-specific
│   └── frontend/
│       └── typescript.md         # Domain-specific
├── guides/
│   ├── docs/
│   │   ├── writing-a-guide.md   # Category-specific
│   │   └── writing-a-topic.md   # Category-specific
│   └── frontend/
│       ├── writing-unit-tests.md      # Domain-specific
│       └── writing-component-tests.md # Domain-specific
└── skills/
    └── neo4j-cypher-guide/
        ├── SKILL.md
        └── references/
            ├── deprecated-syntax.md
            ├── subqueries.md
            └── qpp.md
```

### Bad Organization

```text
dev/
├── guidelines/
│   └── everything.md            # Too broad, should be split
├── guides/
│   └── all-frontend-guides.md    # Too broad, should use subdirectory
└── knowledge/
    └── architecture-and-deployment-and-data-model.md  # Multiple concepts
```

## See Also

- `dev/adr/0001-context-nuggets-pattern.md` - Decision record for this pattern
- `dev/README.md` - Quick navigation guide
- `AGENTS.md` - Root-level map and glossary
