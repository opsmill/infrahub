# Phase 3d — Architecture and decisions

The challenge reviewer sees only the requirement and the diff, and the design reviewer checks how
the code is built. Neither asks whether the change fits how the system is designed, or what the
change decides and why. Run this phase when the manifest has a `frontend`, `backend` or `other`
area; skip it for a change limited to docs, specs and changelog fragments.

## Inputs

Spawn one reviewer (read-only) with `git diff origin/<base>...HEAD`, the manifest's file list, and
these paths to read with the Read tool before the code:

- the architecture article of each area the change touches: `dev/knowledge/backend/architecture.md`,
  `dev/knowledge/frontend/architecture.md` and `.agents/rules/frontend-architecture.md`
- `dev/adr/README.md`, then every ADR whose title names a part of the system the change touches
- the "Ask First" lists in `AGENTS.md`, `backend/AGENTS.md` and `docs/AGENTS.md`
- the feature's `spec.md` and `plan.md` when `dev/specs/<feature>/` exists, and the PR description
  (`gh pr view <n> --json body`) when a PR exists: they are where a decision's reason is written

The reviewer starts its answer with `READ:` and one line per file read, as in the rule check.

## Questions

Each answer cites `file:line`, and the document it relies on as `path:line`.

- **Layer.** For each new class, function, module, query or component, which layer owns that
  responsibility according to the architecture article, and is the code there? (P2)
- **ADRs.** Does the change contradict an Accepted ADR? (P1)
- **Decisions.** List each decision the change makes:
  - a new dependency
  - a new public contract: a GraphQL query, mutation or field, a REST endpoint, an event, a
    message, a schema node or attribute, a setting or environment variable, a CLI option
  - a data model change, a migration or a database index
  - where the work runs: in the request, in a Prefect workflow, in a worker, or in the frontend
  - stored state or a cache
  - a new pattern where the codebase already has one for the same job

  For each, name the alternative the codebase already uses (`file:line`) and where the reason for
  the choice is written: the spec, the plan, an ADR, the PR description or a commit message.
- **Ask First.** Does the change do something an "Ask First" list names, with no written record
  that it was agreed? (Ask)
- **Reversal.** A public contract, a migration or a stored format is hard to undo once released.
  Is there one with no written reason? (Ask; P3 for an internal choice with no written reason)
- **Failure.** For each new step that writes data or calls another service, what is left when
  it fails partway: after a worker restart, a database error, or a remote that does not answer?
  Can it run again safely? (P2 when an article or rule covers it, P3 otherwise)
- **Scale.** How does the cost grow with the number of nodes, branches or schema kinds? Flag a
  query or request run once per item. (P2, per `dev/guidelines/backend/checklist.md` for the
  backend)

## What Phase 5 does with the findings

A finding graded Ask becomes a question for the author that names the decision and the missing
reason, or Defer with a sentence to add to the PR description when the reason exists but is not
written down. A Layer or ADR finding whose fix would move code between layers is Ask: it changes
the approach, which is the author's decision.
