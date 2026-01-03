# Developer Documentation

Internal documentation for contributors. For user-facing docs, see `/docs/`.

## Quick Navigation

| I want to... | Go to |
|--------------|-------|
| Understand the architecture | `knowledge/` |
| Follow coding standards | `guidelines/` |
| Learn why we made a decision | `adr/` |
| Complete a specific task | `guides/` |
| See what's being built | `specs/` |
| Explore rough ideas | `explorations/` |
| Use agent commands | `commands/` |

## Directory Guide

- **explorations/**: Rough ideas, spikes, "what if" thinking. Not approved.
- **specs/**: Approved designs. Living during development, then archived.
- **guidelines/**: Prescriptive rules. How code should be written.
  - `backend/` - Python backend standards
  - `frontend/` - TypeScript/React frontend standards
- **knowledge/**: Descriptive reference. How the system works.
  - `backend/` - Backend architecture and patterns
  - `frontend/` - Frontend architecture and patterns
- **guides/**: Step-by-step procedures for specific tasks.
  - `docs/` - Documentation-specific guides
  - `frontend/` - Frontend-specific guides
- **adr/**: Architecture Decision Records. Why we chose what we chose.
- **commands/**: Reusable agent commands (canonical source).
- **prompts/**: Prompt templates for common thinking tasks.
- **skills/**: Domain-specific skill guides for AI agents (e.g., Neo4j Cypher).

## Document Lifecycle

```text
explorations/ → specs/ → knowledge/ or guidelines/
   (rough)     (approved)      (stable)
```

Mark deprecated docs clearly. Don't delete—update with pointers to replacements.

## Current Guidelines

- **Repository Organization**: `guidelines/repository-organization.md` - How to organize content in dev/
- **Python Backend**: `guidelines/backend/python.md`
- **TypeScript Frontend**: `guidelines/frontend/typescript.md`
- **Git Workflow**: `guidelines/git-workflow.md`
- **Markdown Formatting**: `guidelines/markdown.md`
- **Writing Documentation**: `guidelines/documentation.md` - How to write user-facing documentation

## Current Commands

Available agent commands in `commands/`:

- `_shared.md` - Shared instructions for all flows
- `new-component.md` - React component creation flow
- `guided-task.md` - General task flow
- `add-docs.md` - Documentation flow
- `fix-bug.md` - Bug fixing flow
- `fix-github-issue.md` - GitHub issue fixing
- `fix-mypy-module.md` - Mypy type fixes
- `fix-ruff-rule.md` - Ruff linting fixes
