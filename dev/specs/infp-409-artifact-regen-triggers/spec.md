# Feature Specification: Refactor When Artifacts Are Regenerated on Git Changes

**Feature Branch**: `artifact-regen-triggers-infp-409`
**Created**: 2026-06-01
**Status**: Draft
**Jira**: [INFP-409](https://opsmill.atlassian.net/browse/INFP-409)
**Source investigation**: [`dev/specs/infp-409-artifact-regeneration-investigation.md`](../infp-409-artifact-regeneration-investigation.md)
**Input**: User description: *"Refactor when artifacts are re-generated with regards to changes in a git repo."*

## Background

Today, during a proposed change, every artifact in every artifact definition is regenerated whenever any file changes in any linked Git repository — even if the change is unrelated to that artifact. A typo fix in a README causes the system to regenerate artifacts for thousands of nodes. Customers running with target groups of 10,000+ devices pay a substantial cost for this over-regeneration, both in pipeline latency and in compute. Users also have no visibility into why a particular regeneration happened.

There are three legitimate categories of change that should trigger regeneration:

1. **A data change.** A node read by the artifact's query is modified → only the affected artifacts regenerate.
2. **A new target group member.** A node joins the definition's target group → an artifact is generated for the new member; existing artifacts are not regenerated.
3. **A change to the definition's closure itself.** The query, the transform code, the transform's transitive dependencies, the target-group relationship, the transformation reference, or the manifest entry changes → all artifacts of that definition regenerate.

This feature is specifically about category 3 — closing the gap between "what actually changed in the definition's closure" and "what regeneration the system triggers." The data-change path (category 1) and new-member path (category 2) are already correct today and remain so.

A linked ticket, [IFC-1797](https://opsmill.atlassian.net/browse/IFC-1797), describes the same problem for transform-based computed attributes. This feature is scoped to artifact definitions only; the design is shaped so the computed-attribute path can adopt the same mechanism later without redesign.

The feature delivers value in two stages. The first stage targets the GraphQL query path and the artifact-definition node itself — no schema additions, no SDK coordination, and ships a meaningful reduction in over-regeneration on its own. The second stage adds the transform dependency closure (with the `watch:` field) and requires schema additions plus a coordinated SDK release. The two stages can ship in the same release or sequentially; planning may stage them as needed. **In the interval between the stages**, if stage 1 is deployed before stage 2, transform-file edits still trigger the legacy regenerate-on-any-file-change fallback for definitions whose query did not also change — preserving today's behavior in that subset until stage 2 lands. No new failure mode is introduced by staging.

## Design Principles

**Correctness comes before efficiency. An artifact that should regenerate must always regenerate. Over-regeneration is acceptable; under-regeneration is not.**

This principle drives every design decision in the spec. Whenever the system cannot prove that a change is irrelevant to a definition's output, it regenerates. Every fallback path — the legacy `has_file_modifications` behavior, the `dependencies_complete = False` flag, the null-dependencies rollout fallback — exists to preserve this invariant. A missed regeneration leaves customers with stale artifacts in production; a wasted regeneration costs only compute. The trade is asymmetric and deliberate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Stop regenerating artifacts for unrelated commits (Priority: P1)

A network automation engineer opens a proposed change. The PR contains commits that update a README and adjust an unrelated Python helper module — neither file is used by any artifact's query or transform. Today, every artifact in every artifact definition regenerates. The user wants regeneration to happen only when something that actually affects an artifact has changed.

**Why this priority**: This is the core ticket motivation. It is the screaming pain point for customers and the largest reduction in wasted pipeline work.

**Independent Test**: Open a proposed change that contains only a README edit in a linked Git repository. Verify no artifacts are regenerated. Repeat with an edit to a Python helper module that no transform imports — same expected outcome.

**Acceptance Scenarios**:

1. **Given** a repository with several artifact definitions whose transforms and queries live in `templates/` and `transforms/`, **When** a proposed change modifies only `README.md`, **Then** no artifact is regenerated.
2. **Given** the same repository, **When** a proposed change modifies a `.py` file that is not imported by any tracked transform and is not in any transform's package directory, **Then** no artifact is regenerated.
3. **Given** the same repository, **When** a proposed change modifies a `.gql` file used by exactly one artifact definition, **Then** only artifacts of that one definition are regenerated; other definitions are unaffected.
4. **Given** the same repository, **When** a proposed change modifies the source file of a single transform used by exactly one artifact definition, **Then** only artifacts of that one definition are regenerated; other definitions whose transforms were not modified remain untouched.
5. **Given** the same repository, **When** a proposed change modifies a `.py` file in the same package directory as a transform's `file_path`, **Then** artifacts of definitions using that transform are regenerated (the package-directory heuristic floor includes the file).
6. **Given** a Jinja2 transform whose template uses `{% include "partials/header.j2" %}`, **When** a proposed change modifies `partials/header.j2`, **Then** artifacts of definitions using that transform are regenerated (the transitive closure includes the partial).

---

### User Story 2 — Diagnostic visibility for regeneration decisions (Priority: P1)

When a regeneration does happen, the engineer wants to know exactly which file or change triggered it. Today, the pipeline log simply says "all artifacts will be processed" with no further information, making it impossible to debug unexpected regenerations or to understand which input change is most expensive.

**Why this priority**: Without this visibility, even a correct regeneration decision looks like a black box. Users need to be able to reason about the trigger to trust the new system and to identify their own change patterns that cause excessive regeneration.

**Independent Test**: Open a proposed change that edits one transform file. Verify the pipeline task log contains a clear entry identifying that specific file as the cause of regeneration for the affected definition(s).

**Acceptance Scenarios**:

1. **Given** a proposed change that modifies a transform file, **When** the pipeline runs, **Then** the task log records the specific file path and the affected artifact definition, in a form a user can read.
2. **Given** a proposed change that modifies a GraphQL query, **When** the pipeline runs, **Then** the task log identifies the query (by name) as the cause of regeneration.
3. **Given** a proposed change that modifies an artifact definition's target group relationship, **When** the pipeline runs, **Then** the task log identifies the definition-level change as the cause.
4. **Given** a proposed change that repoints an artifact definition's `transformation` relationship to a different transform, **When** the pipeline runs, **Then** all artifacts of that definition are selected for regeneration and the task log identifies the transformation re-point as the cause.
5. **Given** a transform whose dependencies could not be fully resolved (a dynamic Jinja2 include without an accompanying `watch:` declaration), **When** the import runs, **Then** the task log records each unresolved reference so the user can fix it.

---

### User Story 3 — User-declared dependencies via `watch:` (Priority: P2)

A user has a Jinja2 template that uses a computed include name (`{% include some_var %}`) or a Python transform that imports from a sibling top-level package. Static analysis cannot resolve these dependencies. The user wants a way to tell the system "regenerate artifacts when these files change too," without falling back to "regenerate on every commit."

**Why this priority**: Without this escape hatch, transforms with dynamic dependencies stay in the over-regeneration fallback forever. With it, advanced users can opt their transforms into precise regeneration.

**Independent Test**: Author a Jinja2 transform with a dynamic include and declare `watch.files` covering the candidate directory. Verify edits to files in that directory regenerate the affected artifacts, while edits to other files do not.

**Acceptance Scenarios**:

1. **Given** a Jinja2 transform with a dynamic `{% include some_var %}` and no `watch:` declaration, **When** the user opens a proposed change that edits any repo file, **Then** the affected artifacts regenerate (safe fallback).
2. **Given** the same transform after the user adds a `watch:` entry with a `files:` list covering the candidate templates, **When** the user edits a file in the watched directory, **Then** only the affected artifacts regenerate; **And When** the user edits an unrelated file outside the watch list and outside the auto-detected closure, **Then** no artifact regenerates.
3. **Given** a Python transform that imports from a sibling top-level package, **When** the user declares the package in `watch.files`, **Then** changes to that package trigger regeneration of artifacts using that transform.
4. **Given** any transform, **When** the user provides `watch:` as a YAML list instead of an object, **Then** the schema rejects the input — only the strict object form (`watch: { files: [...] }`) is accepted.

---

### User Story 4 — Safe rollout without operator intervention (Priority: P2)

A platform admin upgrades Infrahub to a version that includes this feature. They have hundreds of existing transforms across many repositories that were imported under the previous version, so none of them have the new dependency metadata yet. The admin wants the upgrade to be safe — no regressions, no manual data migration, no broken pipelines on day one.

**Why this priority**: Forcing operators to run a backfill or take repos offline blocks adoption.

**Independent Test**: Deploy the feature against a database containing transforms imported under the legacy code. Without re-importing anything, run a proposed change and verify the pipeline behaves as it did before the upgrade. Then commit a change to any tracked file in one repository and verify that repo's transforms switch to the new behavior after the natural re-import.

**Acceptance Scenarios**:

1. **Given** a transform whose dependency metadata is absent (never re-imported under the new code), **When** a proposed change touches that repo, **Then** the pipeline falls back to the legacy regenerate-on-any-file-change behavior for that transform — no errors, no missed regenerations.
2. **Given** the same transform after the next commit triggers a re-import, **When** a subsequent proposed change runs, **Then** the new precise regeneration logic applies to that transform.
3. **Given** a repository containing one transform with a malformed Jinja2 template (or an unreadable `watch.files` path) alongside several well-formed transforms, **When** the repository is imported, **Then** the closure-builder failure is logged with the affected transform's identity, the affected transform is marked with `dependencies_complete = False` (forcing safe-fallback regeneration), and the import of the other transforms in the same repository proceeds without error.

---

### User Story 5 — Read-only repositories participate fully (Priority: P2)

A user manages a `CoreReadOnlyRepository` pinned to a specific commit. Different Infrahub branches can pin to different commits of that repo. The branch's `sync_with_git` attribute is set to `False` because read-only repos do not auto-sync. The user opens a proposed change that bumps the read-only repo's pinned commit on the source branch. The user wants this commit bump to be recognized and to trigger appropriate regeneration — the same as for a regular `CoreRepository`.

**Why this priority**: Today, the regeneration gate is conjoined with `sync_with_git`, which silently excludes read-only repos from the file-change path. Customers using read-only repos for shared queries/transforms are stuck with stale artifacts or have to manually flip flags.

**Independent Test**: With a branch having `sync_with_git = False`, bump a linked `CoreReadOnlyRepository` from one commit to another on the source branch where the new commit modifies a transform or query. Verify the affected artifacts regenerate.

**Acceptance Scenarios**:

1. **Given** a branch with `sync_with_git = False` and a `CoreReadOnlyRepository` whose pinned commit on the source branch contains a modified query, **When** the pipeline runs, **Then** the affected artifacts regenerate.
2. **Given** the same setup with a modified transform file, **When** the pipeline runs, **Then** the affected artifacts regenerate.
3. **Given** a `CoreRepository` with `sync_with_git = False` and no commit movement, **When** the pipeline runs, **Then** the file diff is empty and no artifact regenerates on file-change grounds.

---

### Edge Cases

- **Edit-then-revert within the same branch.** The net file diff between source and destination is empty; no regeneration triggers. (Edit-then-revert across different branches, where the file content ends up bit-identical to main, would over-regenerate until the deferred cross-branch fingerprint phase ships — acknowledged as an acceptable trade-off for the first delivery.)
- **`.infrahub.yml` edit anywhere.** Any change to the manifest file in a repo conservatively triggers regeneration for every transform in that repo, even if the edit only affects an unrelated entry. Acceptable trade-off for the first delivery.
- **Symlinks in the transform's package directory or in a `watch.files` entry.** The closure builder skips symlinks silently. Users with symlinks are expected to declare the real target in `watch.files`.
- **Gitignored files, `.pyc`, and `__pycache__`.** Never included in the dependency closure.
- **Both query and transform changed in the same proposed change.** All artifacts of that definition regenerate (either signal alone is sufficient).
- **Two definitions sharing the same query.** A query edit selects both definitions for regeneration.
- **New artifact definition added in the source branch.** A definition that does not exist on the destination branch but is present on the source branch is selected, and artifacts are generated for every member of its target group. This is a distinct code path from "new member of an existing definition's group" (FR-008) — the entire definition is new, not just a member.
- **Closure-builder error at import time** (malformed Jinja2, unreadable `watch.files` path, etc.). The error is logged, the transform's dependency closure is marked incomplete (forcing safe-fallback regeneration), and the import continues for other transforms; the whole import job does not fail.
- **Definition with a non-empty `watch.files` that does not actually cover the dynamic references.** The system trusts the user's assertion and may under-regenerate. Mitigation is documentation and clear logging of unresolved references, not enforcement.

## Requirements *(mandatory)*

### Functional Requirements

#### Regeneration trigger correctness

- **FR-001**: The system MUST NOT regenerate artifacts for a definition when a repository change does not affect any of that definition's inputs (its query, its transform, the transform's transitive dependencies, the artifact definition's own attributes, or the data the query reads).
- **FR-002**: The system MUST regenerate all artifacts of a definition when its associated GraphQL query node is modified. Modifications caused by edits to any `.gql` fragment file the query transitively references are covered automatically: the SDK inlines fragment bodies into the query text at import time, so a fragment edit produces a different stored query value and appears as a node modification in the same way as a primary `.gql` edit. No separate fragment-tracking logic is required.
- **FR-003**: The system MUST regenerate all artifacts of a definition when its associated transform's source file is modified.
- **FR-004**: The system MUST regenerate all artifacts of a definition when any file in the transform's resolved transitive dependency closure is modified.
- **FR-005**: For Jinja2 transforms, the closure MUST include every template referenced via static `{% include %}`, `{% import %}`, or `{% extends %}` directives, resolved transitively.
- **FR-006**: For Python transforms, the closure MUST include every Python file under the package directory containing the transform's `file_path`, excluding `.pyc` files, `__pycache__/`, and any file ignored by git.
- **FR-007**: The system MUST regenerate all artifacts of a definition when the artifact definition node itself is modified in the proposed change (target group repointed, transformation repointed, query repointed, or any other attribute change).
- **FR-008**: The system MUST generate artifacts for new target group members whose artifacts do not yet exist.

#### User-declarable dependencies (`watch:`)

- **FR-009**: The system MUST support a `watch:` field on both `python_transforms` and `jinja2_transforms` entries in `.infrahub.yml`, declared as a strict object containing a `files:` list of paths.
- **FR-010**: The system MUST treat directory entries in `watch.files` as recursive — every file under the directory is part of the closure.
- **FR-011**: The system MUST reject `watch:` declared as anything other than an object (no list/object union), so the schema parses identically in strict-typed SDK languages.
- **FR-012**: The system MUST union the `watch.files` entries with the auto-detected closure when building the final dependency list for a transform.

#### Completeness fallback

- **FR-013**: When the Jinja2 walk encounters a non-literal include name (e.g. `{% include some_var %}`) and no `watch:` is declared, the system MUST mark the transform's dependency closure as incomplete and fall back to today's regenerate-on-any-file-change behavior for that transform — never miss a regeneration.
- **FR-014**: When the user declares a `watch:` with a non-empty `files:` list, the system MUST treat the closure as complete (trusting the user's assertion) even if the auto-detected walk had unresolved references.

#### Path normalization

- **FR-015**: The system MUST normalize file paths to a single canonical form (repo-relative, POSIX separators, no leading `./`, no trailing slashes) before storing them in a transform's dependency list and before comparing them against the git file diff. The same normalizer MUST be applied symmetrically to both sides.
- **FR-016**: The Jinja2 closure builder MUST use the same `FileSystemLoader` root as the runtime renderer (the commit worktree root) so the resulting paths match the canonical convention used by the git diff.

#### Repository handling

- **FR-017**: The system MUST compute file diffs per linked repository, for every Infrahub branch pair, regardless of the branch's `sync_with_git` attribute.
- **FR-018**: For `CoreRepository`, the diff MUST be computed between the source and destination branches' tracked Git branch tips.
- **FR-019**: For `CoreReadOnlyRepository`, the diff MUST be computed between the source and destination branches' pinned commits.
- **FR-020**: When a repository's file diff is empty for a given proposed change, no artifact in that repository MUST regenerate on file-change grounds.

#### Manifest handling

- **FR-021**: The system MUST treat `.infrahub.yml` as part of every transform's dependency closure in that repository. Any edit to the file triggers regeneration of all transforms in that repo for the first delivery (acceptable over-regeneration).

#### Diagnostic logging

- **FR-022**: When the system decides to regenerate all artifacts of a definition, it MUST log an entry identifying the specific cause (the file path, the query, the definition attribute, or the unresolved reference) via the same logger used for other repository import events.
- **FR-023**: When the closure builder fails at import time, the system MUST log the failure with enough context to identify the affected transform and the failure mode, mark the transform's dependency closure as incomplete, and continue importing the remaining transforms.
- **FR-023a**: When the Jinja2 closure builder encounters an unresolved reference, it MUST continue walking the rest of the closure (rather than stopping at the first unresolved reference) and MUST record every unresolved site it finds. This keeps the resulting `dependencies` list useful as a lower-bound dependency set and gives users a complete picture of what needs to be addressed in their templates.

#### Rollout

- **FR-024**: For transforms whose dependency metadata has not yet been populated (imported before this feature deployed), the system MUST fall back to the legacy regenerate-on-any-file-change behavior for that specific transform — without errors and without missed regenerations.
- **FR-025**: When the integrator re-imports a transform under the new code, the system MUST populate the transform's dependency metadata so that subsequent proposed changes use the precise regeneration logic for that transform.

#### Schema location

- **FR-026**: Dependency metadata (`dependencies`, `dependencies_complete`) MUST be stored on the transform's generic kind (`CoreTransformation`), not on each specialization, so the pipeline check is kind-agnostic and future detection mechanisms can be added without schema migration.

### Out of Scope

The following are explicitly out of scope for this feature:

- **Transform-based computed attributes.** Tracked separately under [IFC-1797](https://opsmill.atlassian.net/browse/IFC-1797). The architecture is designed so the same mechanism can be extended later.
- **Generators.** `CoreGeneratorDefinition` uses the same blunt regeneration gate today but does not inherit from `CoreTransformation`. Extending this feature to generators would add the same metadata to `CoreGeneratorDefinition` directly; no design rework is required, just a parallel schema addition and the same pipeline wiring at the generator call site.
- **Cross-branch fingerprint compare** (originally Phase 3 of the investigation). Provides per-entry manifest granularity and edit-then-revert detection across branches. Documented in the investigation as optional and very possibly deferred to an upcoming release. Phase 1 + Phase 2 satisfy the ticket's actual motivation without it.
- **Static analysis of Python imports.** Explicitly rejected — `importlib`, `__import__`, runtime imports, and `exec` on file contents are invisible to AST-precise analysis, and missing one silently violates the correctness invariant. Users with cross-package dependencies declare them via `watch.files`.
- **Verification that a user's `watch.files` actually covers their dynamic references.** Would require knowing what dynamic includes resolve to at runtime, which is the unknowable that prompted asking the user in the first place. Mitigated by clear unresolved-reference logging.

### Known Limitations

These are user-visible boundary conditions that ship with the feature. They are not bugs and not Out of Scope — they are correctness or precision trade-offs the design has deliberately accepted.

- **`dependencies_complete` is effectively a Jinja2-only signal.** Under the current design Python's `dependencies_complete` is always `True` — there is no auto-detection mechanism for Python that produces unresolved references (AST-precise import analysis is explicitly rejected — see Out of Scope). Only the Jinja2 walker can produce a `False`, when it encounters a non-literal include name. A future `watch.strict:` opt-out (deferred) would let Python produce `False` too, which is why the attribute lives on the generic `CoreTransformation` rather than only on `CoreTransformJinja2`.
- **`dependencies_complete` is a guard against omission, not against incorrect declaration.** The flag flips to `False` when the user has dynamic Jinja2 includes and has not declared a covering `watch:`. It flips back to `True` as soon as `watch.files` is non-empty, *regardless of whether that list actually covers the dynamic reference*. A user who declares a `watch.files` list that misses the dynamic resolution target will trust the system into under-regeneration. The unresolved-reference logging (FR-023a) is the user's tool for verifying their `watch.files` covers what the auto-detector found unresolvable.
- **`.infrahub.yml` whole-file conservatism.** Any edit to `.infrahub.yml` regenerates all transforms in that repository, even when the edit only affects an unrelated entry (FR-021). This over-regenerates but is correct; per-entry granularity is a deferred future improvement.
- **Closure rebuild on every commit.** The integrator rebuilds every transform's closure on every commit that affects the repo. For repositories with many transforms this adds parse and walk work to each import. Acceptable for the first delivery; revisit if benchmarks show a regression.
- **Edit-then-revert across branches.** When a source branch's content for a transform is bit-identical to the destination branch's content (despite intermediate edits), the system still regenerates because the file diff is non-empty. Resolving this would require a cross-branch content fingerprint, which is the deferred Phase 3 work.

### Key Entities

- **Artifact Definition** (`CoreArtifactDefinition`): Pairs a GraphQL query with a transform and a target group of nodes to generate artifacts for. Carries a reference to its query, its transformation, and its target group.
- **Transformation** (`CoreTransformation`, with specializations `CoreTransformJinja2` and `CoreTransformPython`): The code that produces an artifact from query data. After this feature, also carries a `dependencies` list and a `dependencies_complete` boolean.
- **GraphQL Query** (`CoreGraphQLQuery`): The query whose result feeds the transform. Already stores the fully-inlined query text (with all fragments resolved), so any change to the query or its fragments is visible as a node modification.
- **Repository** (`CoreRepository`, `CoreReadOnlyRepository`): The Git repository containing transform and query files. Read-only repos are pinned per Infrahub branch; regular repos track a Git branch.
- **Proposed Change**: The change-control unit that opens a comparison between a source and destination Infrahub branch, including per-repo file diffs and a `diff_summary` of node-level changes.
- **Dependency Closure**: The complete set of files (transform source, transitive includes/helpers, watched files, manifest path) whose contents are inputs to a transform's rendered output. Computed at import time and stored on the transform node.
- **`watch:` Object**: A user-supplied configuration on a transform entry in `.infrahub.yml`, currently containing a `files:` list. Extends the closure when automatic detection cannot find all dependencies. Designed as an object so future keys (`strict:`, `exclude:`, etc.) can be added without schema migration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A proposed change whose only file modification is a README edit in a linked repository results in zero artifact regenerations across all artifact definitions in that repository.
- **SC-002**: A proposed change that modifies a single transform's source file (or any file in its declared/auto-detected dependency closure) regenerates only the artifacts produced by definitions that use that transform — not any others.
- **SC-003**: For any pipeline run that regenerates all artifacts of a definition, an engineer can identify the triggering change (file path, query, or attribute) by reading the pipeline task log alone, without cross-referencing the diff or the database.
- **SC-004**: For a target group of 10,000 nodes, the share of pipeline time spent on regenerations triggered by unrelated commits drops to zero in workloads matching SC-001 and SC-002.
- **SC-005**: Upgrading to the version that ships this feature requires no operator-run data migration. Pipelines run correctly on day one; the new precise behavior takes effect per transform on its next natural re-import.
- **SC-006**: Read-only repository commit bumps that contain modified queries or transforms trigger regeneration of affected artifacts, regardless of whether the consuming Infrahub branch has `sync_with_git` enabled.
- **SC-007**: A user with a transform whose dependencies cannot be fully resolved by automatic analysis can declare a `watch.files` list and, on the next re-import, observe that subsequent edits inside the declared paths trigger regeneration while edits outside both the watch list and the auto-detected closure do not.
- **SC-008**: An import-time failure in the closure builder for one transform (malformed template, unreadable path) does not block the import of unrelated transforms in the same repository, and the failure is visible in the repository's task log.
- **SC-009**: No proposed change in any scenario produces a missed regeneration — every artifact whose underlying inputs changed is regenerated, including in the fallback paths (`dependencies_complete = False`, `dependencies is null`).

## Documentation Deliverables

These ship alongside the code in the same release, not as follow-ups:

- **`watch:` schema reference** in the repository config documentation under `.infrahub.yml`. Shows the strict object form with the `files:` key, explains recursive directory matching, notes that future keys (`strict:`, `exclude:`) will live under `watch:`, and gives one example each for `python_transforms` and `jinja2_transforms`.
- **Per-transform rollout note** in the release notes for the version that ships stage 2. States explicitly that the improvement applies to each transform only after that transform has been re-imported under the new code, so users understand the per-transform self-heal behavior and don't expect instantaneous change on upgrade.
- **"Where to find the why trail."** A short section in the artifact documentation pointing users at the repository's task log in Infrahub as the canonical place to see which file, query, or relationship change caused a regeneration. Includes an example log line.
- **`dependencies_complete = False` user guidance.** A short note on what it means when a transform is logged as having unresolved references (typically a dynamic Jinja2 include), and the two fixes available: rewrite the include with a literal name, or declare a covering `watch.files` list. Includes guidance on verifying the `watch.files` against the logged unresolved sites.

## Assumptions

- **Phase scoping per the investigation document.** The deliverable is Phase 1 + Phase 2 from the source investigation. Phase 3 (cross-branch fingerprint compare) is documented as optional and very possibly deferred to an upcoming release.
- **Computed attributes follow later.** This feature targets artifact definitions only. The same closure/dependency mechanism is structured so the IFC-1797 work for transform-based computed attributes can reuse it without redesign.
- **Generators follow later.** Same reasoning; the pipeline check pattern ports cleanly, but generators would need a parallel schema addition because `CoreGeneratorDefinition` does not inherit from `CoreTransformation`.
- **SDK release coordination is required.** The `watch:` schema lives in the Python SDK's repository config model, so a coordinated SDK release is part of the feature delivery. If the SDK release cycle becomes a blocker, the feature can ship with the Python heuristic floor only and `watch:` can land in a follow-up — but this should be a deliberate fallback, not the default plan.
- **The closure-builder load is acceptable on every commit.** Closures are rebuilt at every import of a transform. For repositories with many transforms this adds parse and walk work to each commit. Acceptable for the first delivery; revisit if benchmarks show a regression.
- **The user is the closest authority on `watch.files` correctness.** The system trusts a user-declared `watch:` even if the declaration is wrong; verifying correctness would require knowing what dynamic references resolve to at runtime, which the system fundamentally cannot do.
