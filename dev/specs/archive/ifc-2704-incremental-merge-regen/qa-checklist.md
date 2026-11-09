# QA Checklist — Incremental generator & artifact execution on merge

**Generated**: 2026-07-24
**Feature**: dev/specs/ifc-2704-incremental-merge-regen
**Source**: speckit.opsmill.qa

## Scope

Verify, as an operator of a self-hosted Infrahub, that merging a branch regenerates only the
artifacts and generators the merge affected (not every definition for every member), that the
behavior can be turned off with a config flag, and that a generator running after a direct merge
still refreshes the artifacts that read its output. Out of scope: the automated unit/component
suites (CI), and internal selection internals.

## Prerequisites

- [ ] Working copy on `pmi-20260724-wrap-up-perf` with the implementation built into the image.
- [ ] `uv sync --all-groups` completed cleanly.
- [ ] Branch code is running, not the published image — pin it: `export INFRAHUB_IMAGE_VER=local` and build (`uv run invoke dev.build`) before starting, per `AGENTS.md`.
- [ ] `export INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE=true` (this is the default; set explicitly so Scenario 2 can flip it).
- [ ] A linked repository whose `.infrahub.yml` defines an artifact definition targeting a group of ≥3 members, and one `execute_after_merge` generator feeding another artifact.

## Setup

```bash
export INFRAHUB_IMAGE_VER=local
export INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE=true
uv run invoke dev.build
uv run invoke demo.start
uv run invoke demo.load-infra-schema demo.load-infra-data
# Then add the linked repository through the UI (Object > Repository) or infrahubctl, and wait for its first import to finish.
```

Open the UI at `http://localhost:8000`, confirm the repository shows `operational_status: online`, and that its artifacts have rendered once for every target member.

## Test Scenarios

### 1. Selective narrowing on merge

**What this verifies**: A small merge regenerates only the affected member's artifact.

**Steps**:

- [ ] Note the current `storage_id` of the target artifact for two members (UI artifact view, or a `CoreArtifact` GraphQL query filtered by `object`).
- [ ] Create a branch, change one attribute the artifact's query reads on **one** member, and merge it (UI or `BranchMerge`).
- [ ] Watch the task/activity view for the post-merge follow-up to drain.
- [ ] Confirm the changed member's artifact has a **new** `storage_id`; the untouched member's `storage_id` is **unchanged**.

**Expected result**: Only the affected member's artifact re-renders. The activity view shows a handful of regeneration tasks, not one per definition per member.

### 2. Reversible rollout via the config flag

**What this verifies**: Disabling the flag restores the prior full-regeneration behavior.

**Steps**:

- [ ] Set `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE=false` and restart: `uv run invoke demo.stop demo.start`.
- [ ] Repeat the single-member change and merge from Scenario 1.
- [ ] Watch the activity view.

**Expected result**: Every definition is regenerated for every member (one regeneration task per definition per member), matching the pre-feature baseline — visibly more tasks than in Scenario 1. Re-enable the flag afterward.

### 3. Generator-to-artifact cascade on a direct merge

**What this verifies**: An artifact reading a generator's output is refreshed after a direct merge.

**Steps**:

- [ ] Re-enable the flag (`true`) and restart.
- [ ] On a branch, change data that the `execute_after_merge` generator reads for one member, and merge directly (not through a proposed change).
- [ ] Let the follow-up drain.
- [ ] Confirm the generator ran for that member (its written attribute updated) **and** the artifact consuming that attribute shows the new value.

**Expected result**: The generator's output and its downstream artifact are both current — no stale artifact left behind, and unrelated members are untouched.

## Edge Cases

- [ ] No relevant change: merge a branch changing only data no definition reads → the activity view shows no generator run and no artifact regeneration.
- [ ] Incomplete closure: a transform with a dynamic `{% include some_var %}` shows `dependencies_complete: false` and regenerates on any repo change; adding `watch.files` for it in `.infrahub.yml` (then committing) restores precise regeneration.
- [ ] Fresh import: a repository imported before this feature has no fingerprints; the first merge after re-import regenerates its whole repository once, then narrows on subsequent merges.

## Teardown

```bash
uv run invoke demo.destroy
unset INFRAHUB_IMAGE_VER INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE
```

## Sign-off

- [ ] All scenarios above pass.
- [ ] No unexpected output, warnings, or errors observed.
- [ ] Tester: ______________________  Date: __________
