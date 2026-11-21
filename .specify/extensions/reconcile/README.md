# Spec-Kit Reconcile

A Spec-Kit extension to reconcile documentation with implementation drift.

## Overview

`speckit.reconcile.run` records discoveries the team has accepted in a feature's own artifacts. You describe what drifted in plain language; the command resolves the feature's paths, edits the sections of `spec.md` and `plan.md` the drift actually reaches, and appends remediation tasks to `tasks.md`.

It is optional, opt-in reconciliation that sits outside the core workflow, as Spec Kit's [spec persistence docs](https://github.com/github/spec-kit/blob/main/docs/concepts/spec-persistence.md) describe for extensions. It can run during delivery (it is offered after `/speckit.implement`) or after it, whenever the team has accepted a discovery that the feature's own artifacts do not record yet. The code is evidence for that decision, not the source of intent: what gets written comes from the gap report and the team's approval.

## Features

- **Gap report input**: Free-form notes about what was missed or changed during implementation. The report steers the run without overriding it. It can direct attention and emphasis, but it cannot widen the source boundary, skip a check, change the scope, renumber anything, or authorize a deletion. Ask for one of those and the command refuses that part, finishes the run anyway, and names the refusal in its report. The report is also echoed verbatim, so every run stays auditable.
- **Bounded inputs**: The command declares every file it may take content from. Git history, deleted files, another feature's spec directory, bug reports and agent memory stores are not sources. It may read the repository's own source files, read-only, for exactly one purpose: turning a described target ("the sidebar") into a real path. No task path is ever invented. When none resolves, the task names its target without a path and the omission is reported, because a task pointing at a file that does not exist gets discovered during implementation, while an honest one gets discovered during review. A route the report never names is handled the same way: the plan entry records the drift and marks the path position `[NEEDS CLARIFICATION]` instead of guessing a plausible URL.
- **Full spec coverage**: Amends whichever sections the drift reaches, among Functional Requirements, Acceptance Scenarios, Edge Cases, Key Entities, Success Criteria and Assumptions, and leaves the rest alone. Where the drift reaches a section the file lacks, the command creates it in the position the template puts it and reports the creation.
- **Previewed targets**: Before any edit, the run prints a target table naming the existing item each amendment will land on, by ID or by quoted phrase, with the counts behind it. Without that preview the same choice made twice can come out two different ways, and a zero stays ambiguous when it needs to read as "examined and found nothing to amend" rather than "did not look".
- **Remediation tasks**: New `T###` entries in `tasks.md`, continuing whatever numbering convention the file already uses, and never marked `[P]`. They land under the existing phase heading that covers the affected story, or under a `## Remediation: Gaps` section when no phase does.
- **Safe to re-run**: Tasks carry a `[Sync: ...]` tag, and revision notes carry the same slug plus the list of items they touched. A refined version of the same gap report updates the earlier result instead of duplicating it, and a re-run amends the same entries instead of finding them again by prose. Idempotency is judged per artifact, so a scope-limited run is not mistaken for a completed one.
- **Explicit approval**: Before any edit, the run lists the drift items it found and asks which ones the team approves reconciling into the artifacts: for a behaviour change, that the shipped behaviour is now intended; for missing work, that the gap should be recorded and remediation tasks added. An item you do not approve is written nowhere, and the report recommends `/speckit.converge` for it, which checks the code against the artifacts as they stand. A gap report saying "approved" does not skip the question, so every run is interactive, except under a flow-forward constitution, where nothing is asked or written. The approved items are recorded on an `Approved:` line in each revision note, so the decision stays on record next to the edits it allowed.
- **Respects the persistence model**: When the constitution states that the project uses flow-forward, where completed artifacts are immutable, the run writes nothing and recommends a new feature directory instead. This holds on every run, including one during delivery, because under that model any change goes into a new feature directory. Under flow-back, living spec, or no stated model, it reconciles normally. If an open `/speckit.converge` task was written against an entry the run amends, or one an earlier run amended under the same slug, the run names that task so the team can resolve it before implementing.
- **Back to delivery**: The "Next Step" routes to `/speckit.converge` whenever an artifact changed, after `/speckit.implement` when remediation tasks were added, so converge checks the code against the updated artifacts.
- **Enforced verification**: Any wiring or navigation gap the run discovers gets a mandatory integration test task.
- **Constitution compliance**: Checks the rules the drift reaches, in the three ways a MUST rule can fail. A *conflict* is a remediation item that contradicts a rule; you are asked about it, and one left unresolved withholds that item alone while the rest of the gap report is reconciled and the run completes. An *unmet obligation* is a rule requiring a statement the feature never makes. You are asked, it never withholds anything, and the command will not write the statement for you, since a remediation task directing the author to make it is the honest remedy. An *action-requiring* rule ("all API routes MUST have automated tests") is reported as unverified rather than flagged, because this command reads artifacts and cannot inspect a test run.
- **Aware of other writers**: Other commands patch the same three files, and this one reads what they leave behind. Wording struck through by a bugfix patch is never restored, `**Bugfix**:` lines stay as metadata, and a task reopened by a bug counts as incomplete but is never repurposed. Entries a revision marked `RETIRED`, `SUPERSEDED by [ID]` or `CANCELLED` are read the same way: the marker records a decision somebody already made, so the amendment lands on the live entry and the marked one is reported instead of revived.
- **Reporting**: Absolute paths throughout, a per-finding constitution disposition, an explicit sources declaration, and a conditional "Next Step" that routes to `/speckit.archive.run` when the reconciled feature has already been archived. The [`archive` extension](https://github.com/stn1slv/spec-kit-archive) is an optional companion, not a requirement. It owns both that command and the `.specify/memory/changelog.md` this check reads, so a project without it simply never sees the recommendation.

## Installation

You can install this extension via the Spec-Kit CLI:

```bash
specify extension add reconcile --from https://github.com/stn1slv/spec-kit-reconcile/archive/refs/tags/v1.3.1.zip
```
*(Note: Replace `v1.3.1` with the latest release version)*

To upgrade an existing installation, add `--force`. Without it the CLI refuses to overwrite the installed version:

```bash
specify extension add reconcile --from https://github.com/stn1slv/spec-kit-reconcile/archive/refs/tags/v1.3.1.zip --force
```

`specify extension update` does not work for this extension, and will not in future: the community catalog is deliberately discovery-only (`install_allowed: false`), so `update` skips everything in it rather than pulling unvetted third-party code. `--from` with an explicit URL is the supported upgrade path. To find that URL without leaving the CLI:

```bash
specify extension info reconcile   # prints a "Candidate archive" URL for review
```

Requires Spec Kit 0.16.2 or newer. The command resolves templates through the override stack that release introduced, so an older CLI would read the base template and ignore any preset layered over it.

## Usage

Name the feature, then describe the drift in plain text:

```bash
/speckit.reconcile.run specs/007-invoice-settings Backend exists, but the React screen is unreachable; need sidebar link and route
```

The feature path is required and must resolve to exactly one existing directory; a unique numeric prefix such as `specs/007` is accepted. This command rewrites `spec.md`, `plan.md` and `tasks.md` in place, so it never infers which feature you meant.

**One feature per run.** There is no batch or range mode. `specs/001 thru specs/008` and `specs/00*` are rejected, and so is a second `specs/` path anywhere in the input. Refer to another feature by name in prose ("the invoice feature") when the report has to mention one. Ordinary prose, punctuation, numbers inside sentences and source paths such as `src/router/index.ts` are all fine.

Re-running the same gap report is safe: it updates what it already wrote instead of appending a second set of tasks, and it never edits a task `/speckit.implement` has already marked complete.

**On a brownfield feature, keep the gap report narrow.** A spec written for an existing codebase deliberately covers only the change it introduces, not a retroactive account of everything already there. So "the code does X and the spec never mentions it" is the expected state for anything outside that scope, not drift. Scope the report to the change the spec claims to cover; a broad one will back-fill out-of-scope behaviour into a spec that was meant to stay narrow.

The extension registers optional hooks on `after_implement` and `after_converge`, so both commands offer the reconcile step when they finish. They are prompts, never automatic runs, since the command needs a gap report and will not invent one.

The command also declares `handoffs`, which render as follow-on buttons. Those appear only on agents that install commands as files. The twenty or so agents using the skills layout, Claude Code and Copilot among them, build their skill frontmatter from scratch and drop the key. Nothing is lost either way, because the run's own `## Next Step` section does the same routing in text on every agent.

You can optionally restrict the scope of the updates, placing the modifiers immediately after the feature path:
- `--spec-only`: update only `spec.md`
- `--plan-only`: update only `plan.md`
- `--tasks-only`: update only `tasks.md`

Several modifiers combine as a union: `--spec-only --tasks-only` writes both and nothing else. Modifiers are also still recognised as trailing tokens at the very end of the input, which is how earlier versions accepted them. That position is ambiguous when the report's own last words look like a flag, so the leading position is preferred and the run states its interpretation when it has to guess.

## How this differs from `/speckit.converge` and `/speckit.analyze`

Two core commands sit near this one, and the three take their intent from different places.

| Command | Source of intent | Reads | Writes |
|---|---|---|---|
| `/speckit.converge` (core) | the **artifacts** | spec, plan, tasks, the constitution, plus the codebase | appends remaining work to `tasks.md`, append-only |
| `/speckit.analyze` (core) | the **artifacts** (it compares them) | spec, plan, tasks, the constitution | nothing; it reports inconsistency |
| `/speckit.reconcile.run` | the **team's approved decision**, as the gap report states it | spec, plan, tasks, the constitution | amends `spec.md` and `plan.md`, appends remediation tasks |

`converge` is part of the core delivery loop: it checks the code against the artifacts and appends the work that remains. This command is opt-in reconciliation provided by an extension: it records a discovery the team has decided to accept. After reconciling, run `converge` again, so it checks the code against the updated artifacts. A converge `unrequested` or `contradicts` finding is not a reason to run this command on its own, since converge's task already allows the team to review and justify the code or remove it. It becomes one only when the team decides that the behaviour the code shows should become the intended one. This command never writes into a `## Phase N: Convergence` section, so their outputs stay separable.

Where a requirement is *changing* rather than drifting, meaning the product decided differently and an existing requirement is now wrong, neither command is the right one. That is a revision, and this command will not revive an entry a revision has already marked `RETIRED` or `SUPERSEDED`.

## Workflow

1.  **Parse the gap report** to determine what drift occurred, rejecting ranges, globs, a second feature, and unknown flags before anything is written.
2.  **Resolve paths**: read `REPO_ROOT` from the core `check-prerequisites.sh` script, then resolve the feature under it from the path you passed. A disagreement with the script's own feature is reported.
3.  **Normalize gaps** into categories (Wiring & Navigation, Contracts, Test Coverage, and so on) and check them against the constitution rules they reach.
4.  **Ask for approval**: which drift items the team has accepted. Items left out are withheld.
5.  **Preview**: an impact map and a target table naming the item each amendment will land on, before any edit.
6.  **Edit** the feature's own `spec.md`, `plan.md`, and `tasks.md`, and nothing else.
7.  **Output a Sync Impact Report** detailing the created tasks and next steps, such as routing to `/speckit.implement` and then `/speckit.converge`.

## Tests

`tests/fixture/` holds a minimal spec-kit project with deliberate traps and a pre-registered `EXPECTATIONS.md`. A test runner is a fresh agent given only `commands/reconcile.md` and its own working copy; its output is compared to the expectations. Expectations for a round must land in a commit **before** that round's runs, so the claim "written first" is auditable.
