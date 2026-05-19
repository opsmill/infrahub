---
paths:
  - "backend/infrahub/**/*.py"
---

# Code documentation style

Applies to docstrings, comments, and any inline documentation in Python source files.

## No references to other code

Do not name other classes, functions, methods, callers, or call sites in docstrings or comments. Examples of what to avoid:

- "Used by `FooService` to ..."
- "Called from `handle_request` after authentication"
- "See also `BarMapper.transform`"
- "Mirrors the behavior of `LegacyClient`"

Why: code is renamed, moved, and deleted. These references rot silently and mislead readers. Well-named identifiers and grep make the relationships discoverable without the comment.

Acceptable exceptions:

- Stable public API contracts (e.g. a protocol/interface that other implementations must satisfy) — name the protocol, not its callers.
- A workaround that depends on a specific upstream library symbol — name the library function and version constraint.

## No work-item or spec IDs

Do not reference Jira tickets, GitHub issues, or spec-kit identifiers in docstrings, comments, or test names. Examples of what to avoid:

- `# Fixes INFP-556`
- `"""Implements FR-003: ..."""`
- `# T042: validate payload`
- `# See https://github.com/opsmill/infrahub/issues/9257`

Why: these belong in the commit message and PR description. In source, they become noise once the ticket is closed and the codebase has moved on.

Where IDs *do* belong:

- Commit messages, PR titles/descriptions
- Changelog fragments under `changelog/`
- Spec/plan/tasks files under `dev/specs/`

## What good documentation looks like

- Explains *why* the code exists when the why is non-obvious (a constraint, an invariant, a workaround for a specific upstream bug).
- Documents the contract of a public function (inputs, outputs, errors raised) when it crosses a module boundary.
- Stays silent by default. A comment that restates the code is worse than no comment — it adds noise and rots the moment the code changes.
