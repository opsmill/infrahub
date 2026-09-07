---
paths:
  - "backend/**/*.py"
  - "python_testcontainers/**/*.py"
  - "tasks/**/*.py"
  - "utilities/**/*.py"
  - "tests/**/*.py"
  - ".agents/**/*.py"
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
---

# Code documentation style

Applies to docstrings, comments, and any inline documentation in source files — Python and TypeScript alike.

Never leave comments that narrate what the change is doing or restate the code below them ("// fetch the user", "# loop over the results"). Reviewers repeatedly have to ask for these to be removed.

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

Spec **vocabulary** goes the same way as spec IDs. A phrase coined in a spec ("the unsound package-directory floor") means nothing to a reader who never read that spec, and test names and docstrings are read by people who never will. Say what the code does in plain terms instead.

Where IDs *do* belong:

- Commit messages, PR titles/descriptions
- Changelog fragments under `changelog/`
- Spec/plan/tasks files under `dev/specs/`

## What good documentation looks like

- Comment the *why*, never the *what*: a constraint, an invariant, a workaround, a deliberate deviation from the obvious approach. Never paraphrase the line below it or restate the type signature.
- Documents the contract of a public function (inputs, outputs, errors raised) when it crosses a module boundary.
- Stays silent by default. If code needs a comment to explain *what* it does, rename or extract until it doesn't. A comment that restates the code is worse than none — noise that rots the moment the code changes.
- When a why-comment is warranted, one sentence. If the why needs a paragraph, it belongs in the function's docstring or a `dev/knowledge/` page, not inline. Reviewers repeatedly ask for multi-line inline comments to be condensed.
- Don't narrate the approach *not* taken, and don't narrate the code's history. A paragraph on the alternative rejected, or the call deliberately avoided, belongs in the PR description; keep the line stating what the code does. A comment describes what the code does from now on, never what it used to do or why the old shape was wrong — sweep your additions for "used to", "no longer", "previously", "was rejected", "would have". A negative statement that is part of the contract stays — "this never raises", "does not commit the transaction", "not thread-safe".
