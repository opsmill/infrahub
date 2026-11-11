# Review instructions

## What Important means here

Reserve Important for findings that would break behavior or data: incorrect logic, a migration that is not backward compatible, a GraphQL or REST change that breaks existing clients, and a missing permission check. Style, naming and refactoring suggestions are Nit at most.

## Cap the nits

Report at most five Nits. Put any further small points in one list at the end of the summary, so they are recorded without becoming findings.

## Do not report

- What CI already checks: ruff, mypy, Biome, markdownlint, vale and stale generated files
- The generated files listed in `AGENTS.md`
- Changes inside the `python_sdk/` and `frontend/packages/schema-visualizer/` submodules

## Always check

- Name in the summary any change that `AGENTS.md` says needs agreement first: database schema or migrations, the GraphQL schema, new dependencies, CI workflows, and authentication or permissions.

## Product and user impact

For a change users can see in the UI, the API, the CLI or the documentation, also report:

- Product: the pull request does more than one thing, or leaves out something its linked issue asks for.
- User: an empty state, error message or permission denial that does not tell the user what happened and what to do next.

## Evidence

A finding about behavior cites `file:line` in the source, not an inference from a name.

## Docs

A missing docs update and a language problem are Nit at most and share the five-Nit cap. Rank a docs sentence that the code contradicts first, then a missing docs update, then language. Two docs problems are Important: a missing `COPY` line in `development/Dockerfile` that breaks the container image build, and customer or personal data in the docs.
