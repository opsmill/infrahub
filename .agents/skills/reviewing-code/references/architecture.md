# Architecture and decisions

Checks whether the change fits how the system is designed, and what it decides and why.

Give one reviewer `git diff origin/<base>...HEAD`, the manifest's file list, and these files:

- the architecture article of each area the change touches: `dev/knowledge/backend/architecture.md`,
  `dev/knowledge/frontend/architecture.md`, `.agents/rules/frontend-architecture.md`
- `dev/adr/README.md`, then each ADR whose title names a part of the system the change touches
- the "Ask First" lists in `AGENTS.md`, `backend/AGENTS.md` and `docs/AGENTS.md`
- the feature's `spec.md` and `plan.md`, and the pull request description when one exists:
  this is where the reason for a decision is written

## Questions

- **Layer.** Is each new class, function, module, query or component in the layer the
  architecture article gives that responsibility? (P2)
- **ADRs.** Does the change contradict an Accepted ADR? (P1)
- **Decisions.** List each decision the change makes:
  - a new dependency
  - a new public contract: GraphQL query, mutation or field, REST endpoint, event, message,
    schema node or attribute, setting, environment variable, CLI option
  - a data model change, a migration or a database index
  - where the work runs: the request, a Prefect workflow, a worker, the frontend
  - stored state or a cache
  - a new pattern for a job the codebase already does another way

  For each, name the alternative the codebase uses (`file:line`) and where the reason is written.
- **Ask First.** Does the change do something an "Ask First" list names, with no record that it
  was agreed? (Ask)
- **Reversal.** Is there a public contract, migration or stored format with no written reason?
  (Ask; P3 for an internal choice)
- **Failure.** For each new step that writes data or calls another service, what is left when it
  fails partway (worker restart, database error, remote not answering), and can it run again
  safely?
- **Scale.** Flag a query or request that runs once per node, branch or schema kind. (P2 for the
  backend, per `dev/guidelines/backend/checklist.md`)

## In Phase 2

An Ask finding becomes a question that names the decision and the missing reason. When the
reason exists but is not written down, the finding is Defer, with a sentence for the pull request
description. A Layer or ADR finding whose fix moves code between layers is Ask.
