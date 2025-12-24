# 1. Context Nuggets Pattern for Repository Organization

**Status:** Accepted
**Date:** 2024-12-24
**Author:** @opsmill-team

## Context

As we scale our projects and integrate more AI agents alongside our team, we face a crucial challenge: maintaining velocity without sacrificing structure. AI coding assistants like Claude Code, Cursor, and others need context about our project to generate appropriate code, but traditional approaches have limitations:

1. **Context Window Overload**: A single large `AGENTS.md` file becomes unwieldy, causing AI agents to overfit on irrelevant content or miss important constraints buried in thousands of lines.

2. **Tool-Specific Configuration**: Each AI tool wants its own configuration:
   - Claude Code reads `CLAUDE.md`
   - Cursor uses `.cursor/rules/*.mdc`
   - Others converge on `AGENTS.md`
   This creates duplication, inconsistency, and maintenance burden.

3. **Discoverability**: When everything is in one place, nothing is findable. Humans and AI agents struggle to locate the specific information they need for a given task.

4. **Decision Traceability**: Without structured documentation, it's difficult to understand why architectural decisions were made, leading to AI agents making choices that conflict with past decisions.

5. **Maintenance Burden**: Large documentation files are hard to review, update, and keep current. Changes become risky because the impact is unclear.

## Decision

We adopt the **Context Nuggets** pattern for organizing our repository, based on the framework developed at OpsMill. This pattern treats documentation like code: small, focused files with clear ownership, linked together rather than duplicated.

### Core Structure

- **Root `AGENTS.md`**: Serves as a lightweight map (~2-3KB) with glossary and pointers to detailed documentation, not a knowledge dump.

- **`dev/` directory**: Centralizes all internal developer documentation as "context nuggets" (200-400 lines each), organized by purpose:
  - `explorations/` - Rough ideas, spikes
  - `specs/` - Approved designs
  - `guidelines/` - Prescriptive rules (how to write code)
  - `knowledge/` - Descriptive reference (how the system works)
  - `guides/` - Step-by-step procedures
  - `adr/` - Architecture Decision Records
  - `commands/` - Reusable agent commands
  - `prompts/` - Reusable prompt templates
  - `skills/` - Domain-specific skill guides for AI agents

- **Tool Compatibility**: Use symlinks to maintain a single source of truth:
  - `.claude/commands` → `dev/commands`
  - `.claude/skills` → `dev/skills`

### Key Principles

1. **Context nuggets, not dumps**: Small, focused files (200-400 lines) covering one concept each
2. **Map, not encyclopedia**: `AGENTS.md` routes to details; it doesn't contain them
3. **Link, don't duplicate**: Cross-reference between files rather than copying content
4. **Treat docs like code**: PRs, reviews, ownership, version control
5. **Task-scoped loading**: Load what's needed for this task, not everything
6. **Document lifecycle**: Documents evolve from explorations → specs → stable reference

## Consequences

### Positive

- **Task-scoped context loading**: AI agents fetch what they need per task instead of loading everything, improving relevance and reducing context window waste
- **Maintainable documentation**: Small files are easier to review, update, and keep current
- **Version-controlled decisions**: ADRs provide permanent record of why decisions were made
- **Clear ownership**: Each file has a clear purpose and can be owned by specific teams/individuals
- **Tool compatibility**: Single source of truth with symlinks eliminates duplication
- **Better discoverability**: Organized structure makes it easier for humans and AI to find relevant information
- **Scalable**: Structure supports growth from small projects to large monorepos

### Negative

- **Initial setup overhead**: Requires upfront investment to organize existing documentation
- **Link maintenance**: Need to actively maintain cross-references; broken links need fixing
- **Learning curve**: Team members need to understand the structure and where to find/create content
- **Potential fragmentation**: Risk of creating too many small files if not disciplined about organization

### Neutral

- **Treats docs like code**: Documentation changes go through PRs and reviews, same as code changes
- **Requires discipline**: Team must follow the structure and not revert to dumping everything in one file
- **Ongoing maintenance**: Structure requires active curation, but less than maintaining monolithic files

## Alternatives Considered

### Single AGENTS.md File

**Why we didn't choose it**: Becomes unwieldy at scale, causes context window overload, difficult to maintain and review. AI agents struggle to find relevant information in large files.

### Tool-Specific Configurations

**Why we didn't choose it**: Creates duplication and inconsistency. Each tool would have its own version of the same information, leading to drift and maintenance burden.

### No Structure

**Why we didn't choose it**: Leads to chaos, repeated questions, AI-generated code that doesn't match patterns, and decisions that conflict with past choices. The maintenance burden of answering the same questions repeatedly outweighs the cost of structure.

### Separate Documentation Repository

**Why we didn't choose it**: Creates disconnect between code and documentation. Documentation should live with code for better discoverability and easier maintenance. Version control provides safety net for all changes.

## Implementation Notes

- The `dev/` directory is separate from `docs/` (user-facing documentation)
- Subdirectories like `backend/`, `frontend/`, `docs/` within `guides/` and `guidelines/` are used for domain-specific organization
- The `skills/` directory extends the base pattern for domain-specific AI agent guidance (e.g., Neo4j Cypher queries)
- File size target is 200-400 lines, with maximum of 500 lines before splitting
- Documents follow a lifecycle: explorations → specs → knowledge/guidelines

## References

- Repository Organization for AI-Assisted Development @ OpsMill
- `dev/guidelines/repository-organization.md` - Detailed guidelines for organizing content
- `dev/README.md` - Quick navigation guide

