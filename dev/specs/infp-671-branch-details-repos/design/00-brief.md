# 00 — Brief: branch details page with repository state

Source: `emil-product-thinking` interview (13 questions). `grilling-ideas` skipped at the user's
request because the interview had already pressure-tested the answers below.

## The request, as written

> Redo the branch details page to also include the git repo changes: list the repos and display
> tasks related to repos. There are already tasks related to the branch, branch action buttons and
> branch details information.

## Why it matters

Someone merged a branch from the branch page while a generator had failed on it, and the artifacts
came out stale. Today the only way to catch that is to open each repo page and then the Tasks page
separately. People merge from the branch page without a proposed change, so the proposed change's
checks never ran.

## Done looks like

When someone clicks Merge on a branch where a repository's latest generator, import or check run
has failed or is still running, a warning names it before the merge goes through. If the page
can't tell, it says so and doesn't show green. Every repository on the branch has a row showing
its commit, its sync time and the latest run of each workflow, linked to that run's logs.

> **Correction (2026-10-02):** decision #3 below, revised twice on 2026-09-23, supersedes the
> first sentence: a repository in Import Error **blocks** Merge by default (an explicit "I
> understand" checkbox overrides it, and the button then reads "Merge anyway"). Only a failed or
> running generator, a running import, or an unknown state **warns**.

## Who reaches this page, and what they were doing before

An engineer who pushed changes to a Git repo tracked by Infrahub, or edited data on a branch, and
who now wants to merge that branch from the UI without a proposed change. Before this page, they
were on the repo's object page and the Tasks page, piecing together whether everything had run.

**No named person yet.** The incident has no name or date attached (this breaks principle 4).
Before phase 4 we need a real person to put the prototype in front of.

## Decisions made in the interview

| # | Decision | Why |
|---|----------|-----|
| 1 | The headline is a warning on the Merge action, not the repo list | People who merged with a failed generator weren't reading the page. The warning has to be where the click happens. |
| 2 | Count only the latest run per repo and workflow on this branch | Failures that a later run fixed would keep the warning on permanently, and people would learn to click past it. |
| 3 | **Revised twice on 2026-09-23 (user):** a repository in `Import Error` **blocks Merge by default**, with the reason shown. An explicit "I understand" checkbox overrides it, and the button then reads "Merge anyway". A failed or running generator, a running import, or an unknown state **warns**, and needs an explicit acknowledgement to merge anyway. | Blocking matches INFP-670's goal that a branch with a failed import can't be merged, and the IFC-3200 canvas copy ("Merging this branch is blocked until the import succeeds"). A generator failure is sometimes expected, so it stays overridable. "Couldn't check" must never look like "all clear". Caveat: this is a UI gate only. A direct `BranchMerge` via API or SDK isn't blocked until INFP-670 adds a backend gate. |
| 4 | Each repo row shows commit, sync time, and latest run per workflow linked to its logs | This is the evidence people currently collect by hand. Anything less and they keep checking the repo pages. |
| 5 | The prototype calculates readiness in the frontend. A backend readiness query is a follow-up | This tests whether the warning changes what people do, without waiting on the backend. It knowingly goes against "Backend is authoritative" (`dev/guidelines/frontend/page-architecture.md`) for the prototype only. |
| 6 | Artifact failures count, shown as their own "Artifacts" row rather than under a repo (confirmed by the user) | Artifact tasks are tagged only with the target node, so they can't be tied to a repo. Leaving them out would hide exactly the kind of stale output from the incident. |
| 7 | Repo rows follow IFC-3200's "Git sync visibility" canvas, sections 4a–4e (confirmed by the user, 2026-09-23) | IFC-3200 is already building that card. The rail extends it instead of competing with it. Git state comes from `sync_status`, not task state, as IFC-3199 requires. |
| 8 | Generator status stays in scope, even though no INFP-671 or INFP-670 ticket covers it (confirmed by the user, 2026-09-23) | The incident was a failed generator. The epics only cover Git sync and import failures, so cutting it would leave the incident unaddressed. This is a new ask to raise against IFC-3202 / INFP-670. |

## Riskiest assumption

**That the frontend can reliably tie a task to a repository.** Git import, sync and merge tasks
are tagged with the repository ID (`backend/infrahub/git/tasks.py`). Generator runs are tagged
with the generator definition, the target nodes, or only the branch
(`backend/infrahub/generators/tasks.py`: `run_generator`, `run_generator_definition`, `request_generator_definition_run`), so they reach a repo only through
`GeneratorDefinition.repository` (`backend/infrahub/core/schema/definitions/core/generator.py`).
Artifact tasks are tagged only with the target node (the `add_tags` call in `backend/infrahub/artifacts/tasks.py::create`). If
the grouping misses any of these, the warning stays silent on the exact failure from the incident.

**Cheapest test:** seed a branch with one failed generator and one failed artifact task, and check
that both repos show as failed before building any UI around it.

## Success measure

Nobody merges from the branch page past a warning that was shown without explicitly clicking
through it.

## Out of scope

- Merges from CI, the SDK, `infrahubctl` or raw GraphQL. Those belong to the backend readiness
  query follow-up, which CI can call.
- Building the backend readiness query itself. It's recorded here as the follow-up.
- Hard blocks with no override. Per decision #3, even an import error can be overridden explicitly.
- Permission-aware action buttons. Today they only check whether you're logged in. That's a known
  gap, not solved here.
- Merges through a proposed change. It already has checks.
- Redesigning the Data, Files, Artifacts and Schema diff tabs.

## Where it's used

**Desk only** (confirmed by the user). `emil-mobile-native` does not run.

## Still unresolved

- Who merged in the incident, and when.
- How much of the rest of the page changes, beyond the repo section and the Merge warning.
- Whether read-only repositories (`CoreReadOnlyRepository`) are included.

## Current page, for reference

From a read of `src/pages/branches/details.tsx` and `src/entities/branches/ui/`:

- **Header:** name, metadata popover, default or status badge, description.
- **Tabs** (non-default branches only): Details, Data, Files, Artifacts, Schema.
- **Details tab:**
  - Attributes card: name, status if not OPEN, sync with Git, schema differs from default, last
    rebase. `origin_branch` and `created_at` are fetched but not shown.
  - Action row: Merge, Propose change, Rebase, Validate, Delete.
  - Tasks accordion: validate, merge and rebase workflows only, as cards.
- **Repository information on the page today:** only the Files tab, which shows a section per repo
  with its commit range. It shows no sync status and no repo tasks.
