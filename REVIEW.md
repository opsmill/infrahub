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
- Name in the summary a graph migration that this pull request adds and whose only step is to create an index that `backend/infrahub/core/graph/index.py` declares. The API server creates every declared index when it starts, so neither the migration nor its `GRAPH_VERSION` bump is needed. See [Database Indexes](dev/knowledge/backend/database-indexes.md#add-a-missing-index).

## Product and user impact

For a change users can see in the UI, the API, the CLI or the documentation, also report:

- Product: the pull request does more than one thing, or leaves out something its linked issue asks for.
- User: an empty state, error message or permission denial that does not tell the user what happened and what to do next.

## Repeated UI blocks

In a frontend change, look for a UI block that now exists in more than one place:

- A new component or block that repeats an existing one with different values, such as another kind, action or tab. Report it as a Nit and name the existing one by `file:line`.
- A change to a block that also exists in other files. Search for the block's test ID, label or class string, and for any component or hook it uses that few other files import, because a copy made for another value can have a different label and no test ID. Rate a copy the change missed like any other behavior finding, and the same edit made by hand in several copies as a Nit.

`dev/guidelines/frontend/component-patterns.md` says when to extract a shared component.

## Evidence

A finding about behavior cites `file:line` in the source, not an inference from a name.

## Docs

For a change to `docs/` or to behavior a user can see, check the docs against `.agents/skills/opsmill-product-writing-infrahub-docs/rules/_checklist.md` and the rule files it links. Skip the checklist items about the writing workflow, such as the checks file, the gates and the "Rules read" line.

A missing docs update and a language problem are Nit at most and share the five-Nit cap. Rank a docs sentence that the code contradicts first, then a missing docs update, then language. Two docs problems are Important: a missing `COPY` line in `development/Dockerfile` that breaks the container image build, and customer or personal data in the docs.
