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

`group/ux-design` is the one exception: it is applied by humans, never by you.

## What is already handled without you

Two things are decided deterministically by other workflows, so do not spend
effort on them and do not second-guess them:

- **`type/*`** comes from the issue form (`labels:` in the template). Never add one.
- **`group/*`** is mapped from the form's Component dropdown by the `Labeler`
  workflow, for the dropdown options that map to a label with no judgement
  needed. That mapping is the `COMPONENT_TO_LABEL` table in
  `.github/workflows/labeler.yml` (its `issue-component` job) — read it there,
  it is the only place the option list lives.

That mapping only decides when the reporter's selection resolves to **exactly
one** label. The dropdown is multi-select, so it can also resolve to two
different labels (say *Frontend UI* plus *CI/CD*) — picking the primary one is
judgement, so the workflow steps aside and leaves it to you. Selections that
collapse to the same label (*API Server / GraphQL* plus *Git Integration*, both
`group/backend`) still count as one and are handled without you.

You therefore need to supply `group/*` when that mapping could not decide: no
selected option appears in `COMPONENT_TO_LABEL`, the selection resolves to more
than one label, or the issue was created without the form (by an integration, or
by hand). If a `group/*` label is already present, leave it alone.

`category/*` is always yours — no dropdown captures it.

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
- **`category/error-reporting` is the last resort.** If something is genuinely broken
  *and* reported badly, categorise the breakage.
- **Pure rendering/layout bugs get no category.** Overflowing text, cropped elements,
  broken responsive behaviour: apply `group/frontend` alone.
- **If no category clearly fits, apply none.** A missing label is cheap to add later,
  a wrong one is misleading. Do not force a fit.
- **Never replace an existing label.** Only fill in an axis that is missing.
