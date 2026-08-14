# Issue classification taxonomy

Shared by `issue-triage-labeler` (per-issue, on open) and `issue-triage-sweep`
(weekly backfill). Edit here only, both workflows read this file at runtime.

Apply **at most two** labels per issue: one `group/*` (always) and one
`category/*` (bugs only).

**Never apply a priority label.** Priority is assigned by a human.

## 1. Component — `group/*`, always exactly one

Where the fix will most likely land, not where the symptom appears.

| Label | Applies when |
|-------|--------------|
| `group/backend` | API server, GraphQL, task worker, git agent, database, Python code |
| `group/frontend` | React UI: rendering, forms, layout, client-side queries |
| `group/schema` | The core schema definitions themselves (usually alongside `group/backend`) |
| `group/sync-engine` | The external synchronization engine specifically |
| `group/ci` | CI pipeline, GitHub Actions, build tooling |

If a report describes a UI symptom whose cause is clearly server-side (for example a
slow page because a query returns too much data), prefer `group/backend`.

## 2. Category — `category/*`, only when the issue is a bug

Apply a category **only** if the issue is a bug report (it has the `type/bug` label, or
the body describes something behaving incorrectly). For feature requests, tasks,
questions, and documentation issues apply the `group/*` label only.

Pick the **single best** primary category:

| Label | Applies when |
|-------|--------------|
| `category/scaling` | Only appears or gets materially worse with data volume: thousands of nodes, relationships, tasks or events. Timeouts, OOM, slow queries at scale |
| `category/git-sync` | Repository sync/import from Git: read-only repos, `objects/` files, `.infrahub.yml`, commits, tags, clones |
| `category/schema-lifecycle` | Schema load, import, validation, migration, inheritance and attribute definition semantics |
| `category/branching` | Branch create/merge/rebase/diff, proposed changes, conflict handling |
| `category/tasks` | Task manager and Prefect workflow lifecycle: stuck runs, missing/incorrect tasks in the task list |
| `category/generators-artifacts` | Generator, artifact and transform pipeline: definitions, regeneration, execution |
| `category/api` | GraphQL/REST semantics: queries, filters, mutations, events, webhooks, response shape |
| `category/error-reporting` | The defect **is** the message: opaque, misleading, wrong status code, unhelpful traceback. Use only when the underlying behaviour is otherwise correct |
| `category/permissions` | Authentication, authorization, roles, tokens, object permissions |
| `category/pools` | Resource pools: NumberPool, prefix pools, IPAM allocation |

Rules for choosing:

- **One primary category.** Many bugs touch two areas. Pick where the fix belongs.
  A slow diff on a large branch is `category/scaling` if volume is the trigger and
  `category/branching` if the diff is wrong regardless of size.
- **`category/error-reporting` is the last resort.** If something is genuinely broken
  *and* reported badly, categorise the breakage.
- **Pure rendering/layout bugs get no category.** Overflowing text, cropped elements,
  broken responsive behaviour: apply `group/frontend` alone.
- **If no category clearly fits, apply none.** A missing label is cheap to add later,
  a wrong one is misleading. Do not force a fit.
- **Never replace an existing label.** Only fill in an axis that is missing.
