# Issue classification taxonomy

Shared by `issue-triage-labeler` (per-issue, on open) and `issue-triage-sweep`
(weekly backfill). Edit here only, both workflows read this file at runtime.

Apply **at most two** labels per issue: one `group/*` (always) and one
`category/*` (bugs only).

**Never apply a priority label.** Priority is assigned by a human.

## Label definitions

The label definitions live in `.github/labels.yml` (checked out in your
workspace) — the same registry that provisions the labels on GitHub. Read that
file and use the `description` of each `group/*` and `category/*` entry as its
definition. Do not rely on a from-memory idea of what a label means.

A label whose description says it is not applied by automation (today
`group/ux-design` and the legacy `group/schema`) is never yours to apply. Issues
carrying one already have their component axis filled, leave them alone.

## What is already handled without you

**`type/*`** is never yours to add or second-guess. It comes from the issue
form, so an issue opened outside the form (by an integration, or by hand) will
have none — do not read a missing `type/bug` as "not a bug", judge that from
the body.

Both classification axes are yours: `group/*` when the issue is missing one,
`category/*` always — no form field captures it.

A `Component` section in the body is the reporter's own claim about the area,
and it comes in two shapes. The form's dropdown is coarse: multi-select, with
options broader than any one label (*Python SDK*, *Not Sure*), and reporters
guess. Issues opened outside the form often carry precise free text instead
("Task Worker / Proposed change pipeline"), which is usually the best single
signal you have. Weigh it accordingly, but the body's symptoms still decide
when the two genuinely disagree.

## 1. Component — `group/*`, exactly one, only if missing

Pick where the fix will most likely land, not where the symptom appears.

If a report describes a UI symptom whose cause is clearly server-side (for example a
slow page because a query returns too much data), prefer `group/backend`.

## 2. Category — `category/*`, only when the issue is a bug

Apply a category **only** if the issue is a bug report (it has the `type/bug` label, or
the body describes something behaving incorrectly). For feature requests, tasks,
questions, and documentation issues apply the `group/*` label only.

Pick the **single best** primary category:

- **One primary category.** Many bugs touch two areas. Pick where the fix belongs.
  A slow diff on a large branch is `category/scaling` if volume is the trigger and
  `category/branching` if the diff is wrong regardless of size.
- **A proposed-change pipeline bug takes the category of the stage that misbehaved**,
  not `category/branching`. Reserve `category/branching` for the branch and
  proposed-change lifecycle itself: creating, diffing, rebasing, merging, conflict
  handling, merge gates. A generator or artifact that ran in the wrong order inside
  the pipeline is `category/generators-artifacts`.
- **`category/error-reporting` is the last resort.** If something is genuinely broken
  *and* reported badly, categorise the breakage.
- **Internal transport and orchestration defects have no category yet.** A message-bus
  broadcast that does not fan out, or a workflow submitted without waiting, is not
  `category/api` (that axis is the API surface) and not `category/tasks` (that is the
  task list and run lifecycle). Apply `group/*` alone.
- **Pure rendering/layout bugs get no category.** Overflowing text, cropped elements,
  broken responsive behaviour: apply `group/frontend` alone.
- **If no category clearly fits, apply none.** A missing label is cheap to add later,
  a wrong one is misleading. Do not force a fit.
- **Never replace an existing label.** Only fill in an axis that is missing.
