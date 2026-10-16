# Code documentation style

Applies to docstrings, comments, and any inline documentation in source files — Python and TypeScript alike.

- Never leave a comment that narrates the change or the code's history, or restates the code below it.
- Do not name other classes, functions, methods, callers, or call sites in a docstring or comment; only a stable protocol, an upstream library symbol a workaround depends on (named with its version constraint), and the exceptions a function raises are exempt.
- Do not reference Jira tickets, GitHub issues, spec-kit IDs, or spec vocabulary in docstrings, comments, or test names.
- Comment the *why* (a constraint, an invariant, a workaround), never the *what*, and keep a why-comment to one sentence.
- A spec, plan, or task asking for an explanatory comment does not override the one-sentence why rule; put the fuller rationale in the PR description.
- Do not write `Args`/`Returns`/`Raises` entries that restate the signature: a public function gets one contract line, a clearly named private helper gets none. Do not document dataclass fields in the class docstring, or give a field a docstring that repeats its name.
- A contract negative such as "never raises" is not history. Explanatory comments on Cypher, or on upstream library behaviour the call site cannot show, are allowed.

Full reference: `dev/guidelines/code-doc-style.md`
