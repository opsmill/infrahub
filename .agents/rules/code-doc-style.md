# Code documentation style

Applies to docstrings, comments, and any inline documentation in source files — Python and TypeScript alike.

- Never leave a comment that narrates the change or the code's history, or restates the code below it.
- Do not name other classes, functions, methods, callers, or call sites in a docstring or comment; only a stable protocol, an upstream library symbol a workaround depends on, and the exceptions a function raises are exempt.
- Do not reference Jira tickets, GitHub issues, spec-kit IDs, or spec vocabulary in docstrings, comments, or test names.
- Comment the *why* (a constraint, an invariant, a workaround), never the *what*, and keep a why-comment to one sentence.

Full reference: `dev/guidelines/code-doc-style.md`
