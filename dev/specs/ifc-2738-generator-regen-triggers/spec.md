# Feature Specification: Precise Regeneration Triggers for Generators in the Pipeline Based on Git

**Feature Branch**: `generator-regen-triggers-ifc-2738`
**Created**: 2026-06-24
**Status**: Draft
**Jira**: [IFC-2738](https://opsmill.atlassian.net/browse/IFC-2738)
**Implements (JPD)**: [INFP-607](https://opsmill.atlassian.net/browse/INFP-607) — Make generator and artifact execution incremental across all change scenarios
**Input**: User description: *"Precise regeneration triggers for Generators in pipeline based on git."*

## Background

[INFP-409](https://opsmill.atlassian.net/browse/INFP-409) refactored *artifact* regeneration so that, during a proposed change, artifacts only regenerate when something in their actual dependency closure changed in Git, instead of regenerating every artifact on any file change in any linked repository. Generators (`CoreGeneratorDefinition`) use the same blunt regeneration gate today and suffer the same over-execution problem, but were explicitly scoped out of INFP-409 because `CoreGeneratorDefinition` does not inherit from `CoreTransformation`.

This feature extends the INFP-409 mechanism to generators. No new design work is required: the closure-builder framework, path canonicalizer, regeneration predicates, watch-file union, diagnostic logging, and read-only-repository diff decoupling already exist and are reusable. This is parallel wiring plus a core-schema addition on `CoreGeneratorDefinition` and a `watch` field on the SDK's generator config.

Today, in `run_generators` (`backend/infrahub/proposed_change/tasks.py`), a generator definition is dispatched for execution when:

- `DefinitionSelect.FILE_CHANGES`: `source_branch_sync_with_git AND branch_diff.has_file_modifications` — i.e. any file changed in any linked repo, OR
- `DefinitionSelect.MODIFIED_KINDS`: a model the generator's query reads was modified (the data-change path, already correct).

The `FILE_CHANGES` clause is the blunt gate. A README typo in a linked repo re-runs every generator across every target-group member. A second blunt signal lives in `_run_generator` (`tasks.py:1256`), where `managed_branch = source_branch_sync_with_git` force-runs every existing instance whenever the branch syncs with Git. Both are the generator equivalents of the artifact gates INFP-409 replaced.

As with artifacts, there are three legitimate categories of change that should trigger a generator run:

1. **A data change** - a node read by the generator's query is modified. This is the `MODIFIED_KINDS` path; it is already correct today and this feature leaves it unchanged.
2. **A new target-group member** - a node joins the definition's target group, so the generator runs for the new member; existing members are not re-run. This is the `impacted_instances` / per-member path and must remain correct.
3. **A change to the definition's closure** - the generator's source file (or a sibling in its package directory), its `.gql` query, or the definition node itself changes, so all of that generator's instances run.

This feature is specifically about category 3 - replacing the blunt `FILE_CHANGES` gate with precise closure matching. Categories 1 and 2 are already correct and must stay correct: the per-member gate swap (FR-007) is the one place where category 2's `impacted_instances` logic and category 3's predicates interact, which is why it is the primary risk area.

A linked ticket, [IFC-1797](https://opsmill.atlassian.net/browse/IFC-1797), describes the related problem for computed attributes and is tracked separately.

## Design Principles

**Correctness before efficiency. Over-execution is acceptable; under-execution is not.** This principle is inherited verbatim from INFP-409. Every fallback path (null dependencies, incomplete closure, unknown change relevance) must err toward running the generator. A missed generator run leaves stale derived data in production; a wasted run costs only compute. The trade is asymmetric and deliberate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Stop running generators for unrelated commits (Priority: P1)

A network automation engineer opens a proposed change. The PR's only repository change is an unrelated file — for example a `README.md` edit in a linked repository that no generator's source or query depends on. Today every generator runs across every target-group member. The engineer wants generators to run only when something that actually affects a generator's output has changed.

**Why this priority**: This is the core ticket motivation and the largest reduction in wasted pipeline work, mirroring the customer pain that INFP-409 addressed for artifacts.

**Independent Test**: Open a proposed change whose only repository change is a `README.md` edit. Verify that zero generators are dispatched.

**Acceptance Scenarios**:

1. **Given** a repository with several generator definitions whose source files and queries are unrelated to `README.md`, **When** a proposed change modifies only `README.md`, **Then** no generator is run.
2. **Given** the same repository, **When** a proposed change modifies a `.py` file that is not in any generator's package directory and is not read by any generator, **Then** no generator is run.

---

### User Story 2 — Re-run only the generators whose source changed (Priority: P1)

When an engineer edits a generator's source file, or a sibling file within the same package directory, only that generator's instances should re-run. Other generators in the same repository whose source was untouched must not run.

**Why this priority**: Precise source-change targeting is the direct generator analogue of the artifact closure behavior and the primary correctness/efficiency win once unrelated commits are filtered out.

**Independent Test**: Edit the source file of exactly one generator and open a proposed change. Verify that only that generator's instances re-run.

**Acceptance Scenarios**:

1. **Given** a repository with two generators in different package directories, **When** a proposed change modifies the source file of generator A, **Then** generator A's instances re-run and generator B is untouched.
2. **Given** a generator whose `file_path` lives in a package directory containing sibling modules, **When** a proposed change modifies a sibling module in that same package directory, **Then** that generator re-runs (the package-directory floor includes the sibling).

---

### User Story 3 — Re-run only the generators using a changed query (Priority: P1)

When an engineer edits a `.gql` query file, only the generators that use that query should re-run.

**Why this priority**: Query files are a distinct closure input from source code and a common edit target; precise targeting here is required for the feature to be trustworthy.

**Independent Test**: Edit one `.gql` query used by exactly one generator and open a proposed change. Verify that only generators using that query re-run.

**Acceptance Scenarios**:

1. **Given** a repository where a `.gql` query is used by exactly one generator, **When** a proposed change modifies that query, **Then** only generators using that query re-run; other generators are unaffected.

---

### User Story 4 — Read-only repositories participate in precise triggering (Priority: P2)

A generator's closure can live in a read-only repository. When a read-only repository's tracked commit advances and that commit modifies a generator's closure, the generator must re-run even when the consuming branch has `sync_with_git = False`.

**Why this priority**: Read-only repositories are a supported deployment pattern; without participation the feature would silently under-run for those users, violating the correctness invariant. The underlying per-repo diff decoupling already exists from INFP-409 US5, so this is verification rather than new construction.

**Independent Test**: Advance a read-only repository's commit to one that modifies a generator's closure, with the consuming branch set to `sync_with_git = False`. Verify the generator re-runs.

**Acceptance Scenarios**:

1. **Given** a read-only repository whose commit bump modifies a generator's closure, **When** a proposed change is evaluated on a branch with `sync_with_git = False`, **Then** that generator re-runs.
2. **Given** a read-only repository whose commit bump modifies only files outside any generator's closure, **When** a proposed change is evaluated, **Then** no generator runs as a result of that repository.

---

### User Story 5 — Diagnostic visibility for every run decision (Priority: P1)

When a generator runs (or is skipped), the engineer wants the pipeline task log to state exactly which file, query, or definition change triggered the decision.

**Why this priority**: Without trigger visibility, even a correct decision is a black box. Users must be able to reason about why a generator ran in order to trust the new behavior and to identify their own expensive change patterns. This matches the diagnostic guarantee INFP-409 delivered for artifacts.

**Independent Test**: Open a proposed change that edits one generator's source file. Verify the task log identifies that specific file as the trigger for the affected generator's run.

**Acceptance Scenarios**:

1. **Given** a proposed change that triggers a generator run, **When** the run decision is made, **Then** the task log records the specific triggering file, query, or definition change for that generator.
2. **Given** a proposed change that does not trigger a generator, **When** the decision is made, **Then** the log reflects that the generator was not run.

---

### User Story 6 — Backward compatibility and self-healing (Priority: P2)

Generators imported before this feature ships have no stored dependency closure (`dependencies = null`). They must continue to work with no error, fall back to today's behavior, and self-heal to precise triggering on the next re-import.

**Why this priority**: A regression on existing installations is unacceptable. The null-dependencies fallback preserves the correctness invariant during rollout, identical to INFP-409's rollout fallback.

**Independent Test**: Evaluate a proposed change against a generator whose stored `dependencies` is null. Verify it runs under the legacy gate with no error, then re-import and verify it now uses the stored closure.

**Acceptance Scenarios**:

1. **Given** a generator with `dependencies = null`, **When** a proposed change is evaluated, **Then** the generator falls back to today's regenerate-on-file-change behavior with no error.
2. **Given** that same generator, **When** it is re-imported after this feature ships, **Then** its `dependencies` and `dependencies_complete` are populated and subsequent proposed changes use precise triggering.

---

### User Story 7 — Declare extra dependencies via `watch:` (Priority: P2)

A generator imports a helper from a sibling top-level package, or otherwise depends on files outside its own package directory. Automatic detection (the package-directory floor) cannot see those files. The engineer wants to tell the system "also re-run this generator when these files change," without falling back to "run on every commit."

**Why this priority**: Without this, a generator with cross-package dependencies is stuck in the over-run fallback (or silently under-runs if it has a complete package-floor closure that misses the external file). With it, advanced users opt their generators into precise triggering. It is the generator analogue of INFP-409 US3 and is delivered here because the SDK is already being updated.

**Independent Test**: Author a generator that depends on a file outside its package directory, declare that path under `watch.files` in `.infrahub.yml`, and verify edits to it re-run the generator while edits to unrelated files do not.

**Acceptance Scenarios**:

1. **Given** a generator whose `watch.files` lists a sibling package directory, **When** a proposed change edits a file inside that declared directory, **Then** the generator re-runs.
2. **Given** the same generator, **When** a proposed change edits a file outside both the declared `watch.files` and the auto-detected package floor, **Then** the generator does not re-run on file-change grounds.
3. **Given** a generator definition, **When** `watch:` is declared as anything other than the strict object form (`watch: { files: [...] }`), **Then** the schema rejects the input.
4. **Given** a generator whose `watch.files` entry matches no tracked file, **When** the repository is imported, **Then** the mismatch is logged as a warning and the import of that generator and the others proceeds.

---

### Edge Cases

- **Null or incomplete closure**: When `dependencies` is null or `dependencies_complete` is `False`, the system MUST run the generator (never-under-run fallback).
- **Per-member interaction with `impacted_instances`**: The per-member gate in `_run_generator` must preserve the never-under-run invariant when it interacts with the existing `impacted_instances` logic — no instance that should run may be skipped.
- **Generator with no resolvable query peer**: A generator definition whose query reference cannot be resolved must err toward running.
- **Data-change path unchanged**: The `MODIFIED_KINDS` (data-change) path MUST continue to behave exactly as today; this feature only replaces the `FILE_CHANGES` blunt gate.
- **Artifact behavior unchanged**: Generalizing the shared predicates to also serve generators must leave artifact regeneration behavior identical.
- **Two generators sharing one query**: When a `.gql` query is used by more than one generator, editing it selects every generator that uses it.
- **Both query and source changed together**: When a proposed change edits both a generator's query and its source file, the generator runs once (either signal alone is sufficient; they do not double-dispatch).
- **New generator definition on the source branch**: A generator definition that exists on the source branch but not the destination branch is selected and runs for every member of its target group - a distinct path from "new member of an existing definition's group."
- **`watch.files` outside the package directory**: A `watch.files` entry pointing outside the generator's package directory extends the closure to cover it; edits there re-run the generator.
- **`watch.files` that does not actually cover the real dependency**: The system trusts the user's declaration and may under-run if the list is wrong. Mitigation is documentation and clear logging, not enforcement (the system cannot know what runtime imports resolve to).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Schema)**: The system MUST add two optional, nullable attributes to `CoreGeneratorDefinition` directly (it does not inherit `CoreTransformation`), mirroring the INFP-409 attributes: `dependencies` (List/Text) and `dependencies_complete` (Boolean). Generated artifacts MUST be regenerated and committed: `protocols.py`, the generated schema, frontend GraphQL types, and the GraphQL/OpenAPI exports.
- **FR-002 (Closure builder)**: Because generators are Python-only, the system MUST reuse the existing `PythonClosure` builder (package-directory floor). The `TransformConfig` union and `PythonClosure.supports()` MUST be widened to accept `InfrahubGeneratorDefinitionConfig`; `PythonClosure.build()` reads only `file_path` and `name`, both of which are present. NOTE: the shared aggregator runs two further generic steps after the per-language builder - it appends the manifest path (`.infrahub.yml`) and calls the watch-file union, which reads `transform_config.watch`. Once `InfrahubGeneratorDefinitionConfig` gains a `watch` field (FR-014), both steps apply to generators automatically; no aggregator change is needed.
- **FR-003 (Integrator)**: In `import_generator_definitions` (`backend/infrahub/git/integrator.py`), the system MUST build each generator's closure via the existing aggregator (failure isolation already handled) and persist the two attributes through `_create_generator_definition`, `_generator_requires_update`, and `_update_generator_definition`.
- **FR-004 (Pipeline model and gather)**: The system MUST add `query_id`, `dependencies`, and `dependencies_complete` to `ProposedChangeGeneratorDefinition` (`backend/infrahub/generators/models.py`) and populate them in the `client.filters` gather in `run_generators` (`query_id = generator.query.peer.id` plus the two attribute reads).
- **FR-005 (Predicate generalization)**: The predicates `_query_changed`, `_definition_changed`, and `_transform_changed` (currently typed to `ProposedChangeArtifactDefinition`) read only fields that the generator model also exposes under the same names. The system MUST introduce a structural `Protocol` that both models satisfy, and parametrize the "transform"/"artifacts" wording in the diagnostic strings so they read correctly for generators.
- **FR-006 (Definition-level gate swap)**: In `run_generators`, the system MUST replace the `FILE_CHANGES` clause with `_query_changed OR _definition_changed OR _transform_changed(repo_diff)`, keeping the existing `MODIFIED_KINDS` clause unchanged.
- **FR-007 (Per-member gate swap)**: In `_run_generator` / `request_generator_definition_check`, the system MUST make `managed_branch` conditional on the same predicates rather than unconditionally on `source_branch_sync_with_git`. This MUST preserve the never-under-run invariant in its interaction with `impacted_instances`.
- **FR-008 (Read-only repositories)**: Once the gate keys on `_transform_changed(repo_diff)` instead of `sync_with_git`, read-only repositories MUST participate automatically via the shared per-repo diff decoupling from INFP-409 US5. This MUST be verified, not rebuilt.
- **FR-009 (Backward compatibility)**: Generators with `dependencies = null` (imported before this ships) MUST fall back to today's behavior with no error and self-heal on the next re-import.
- **FR-010 (Diagnostics)**: The task log MUST identify the triggering file, query, or definition change for every generator run decision.
- **FR-011 (Tests)**: The system MUST add predicate unit tests (generator-model variants), a `PythonClosure` generator-config support test, a generator-selection component test mirroring `test_artifact_regen_selection.py`, a generator-import closure test, and SDK unit tests for the new `watch` field on `InfrahubGeneratorDefinitionConfig` (parsing, strict-object rejection, recursive directory expansion into the closure). `test_proposed_change_repository.py` (which already runs generators e2e) is `xfail` for GitHub Actions flakiness — the same deferred-e2e blocker as INFP-409.
- **FR-012 (Docs and changelog)**: The system MUST extend the dependency-closure / why-trail documentation to mention generators, add a `watch:` schema-reference entry for generator definitions in the repository-config documentation (mirroring the transform `watch:` reference shipped by INFP-409), and add a Towncrier changelog fragment.
- **FR-013 (Artifact regression safety)**: The shared-predicate refactor (FR-005) touches code paths artifacts also use; the system MUST include regression coverage proving artifact behavior is unchanged.

#### User-declarable dependencies (`watch:`) on generators

- **FR-014 (SDK `watch` field)**: The system MUST add a `watch: InfrahubWatchConfig | None = None` field to `InfrahubGeneratorDefinitionConfig` in the Python SDK (`python_sdk/infrahub_sdk/schema/repository.py`), reusing the existing `InfrahubWatchConfig` model (no new type). The SDK is updated directly in the `python_sdk` submodule; this work is in scope and MUST carry its own tasks, the same as the transform `watch:` work did for INFP-409. Because the closure aggregator already unions `watch.files` and appends the manifest generically, adding the field makes generator `watch:` functional end-to-end with no further backend wiring.
- **FR-015 (Strict object form)**: A generator's `watch:` MUST be accepted only as the strict object form `watch: { files: [...] }` (`extra="forbid"`), identical to transforms, so the schema parses the same way across strict-typed SDK languages. Any other shape MUST be rejected.
- **FR-016 (Closure union and recursion)**: The system MUST union a generator's `watch.files` entries with the auto-detected package-directory floor when building its dependency closure, treating directory entries as recursive (every tracked file beneath them). A `watch.files` entry that matches no tracked file MUST be logged as a warning and MUST NOT silently extend the closure, but MUST NOT abort the import.
- **FR-017 (Completeness with watch)**: When a generator declares a non-empty `watch.files`, the system MUST treat its closure as complete (trusting the user's declaration), consistent with the shared union behavior. The generator otherwise behaves per the never-under-run fallback when its closure is incomplete.

### Key Entities *(include if feature involves data)*

- **`CoreGeneratorDefinition`**: The generator definition node. Gains `dependencies` (the serialized dependency closure of source files and inputs) and `dependencies_complete` (whether the closure is known to be complete). Both optional and nullable for backward compatibility.
- **Dependency closure**: The set of files and inputs (generator source file plus its package-directory floor, any user-declared `watch.files`, the manifest path, and the associated `.gql` query) whose change should trigger the generator. Built by the reused `PythonClosure` and the shared aggregator's manifest-append and watch-union steps.
- **`ProposedChangeGeneratorDefinition`** (`backend/infrahub/generators/models.py`): The in-pipeline representation of a generator definition. Gains `query_id`, `dependencies`, and `dependencies_complete` so the predicates can evaluate it.
- **`watch:` object** (`InfrahubWatchConfig` in the SDK): A user-supplied configuration on a generator entry in `.infrahub.yml`, a strict object containing a `files:` list. Extends the closure when automatic detection cannot reach a dependency (e.g. a sibling top-level package). Reused as-is from the transform `watch:` work; this feature adds it to `InfrahubGeneratorDefinitionConfig`.
- **Regeneration predicates**: `_query_changed`, `_definition_changed`, `_transform_changed` — generalized via a structural `Protocol` to operate on both artifact and generator definition models.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A proposed change whose only repository change is an unrelated file (e.g. README) triggers zero generator runs.
- **SC-002**: Editing a generator's source file (or a sibling in its package directory) re-runs only that generator's instances; no other generator runs.
- **SC-003**: Editing a generator's `.gql` query re-runs only the generators using that query.
- **SC-004**: A read-only repository commit bump that modifies a generator's closure triggers regeneration even when the consuming branch has `sync_with_git = False`.
- **SC-005**: Generators imported before this ships (`dependencies = null`) fall back to today's behavior with no error and self-heal on next re-import.
- **SC-006**: The task log identifies the triggering file, query, or definition change for every generator run decision.
- **SC-007**: Artifact regeneration behavior is provably unchanged by the shared-predicate refactor (regression suite green).
- **SC-008**: The data-change (`MODIFIED_KINDS`) path behaves exactly as before this feature.
- **SC-009**: A generator that declares a `watch.files` path re-runs when files inside that path change and does not re-run for edits outside both the declared paths and the auto-detected package floor; a `watch:` declared in any non-object form is rejected at parse time.

## Scope

### In Scope

Replace the blunt generator gate with the INFP-409 predicate set, store a dependency closure on `CoreGeneratorDefinition`, let read-only repositories participate, and add user-declarable `watch:` dependencies for generators. The in-scope work items are enumerated as FR-001 through FR-017 above: schema addition, closure builder reuse, integrator persistence, pipeline model and gather, predicate generalization, definition-level gate swap, per-member gate swap, read-only-repository verification, tests, docs/changelog, artifact regression safety, and the generator `watch:` field (FR-014..FR-017). This feature touches the `python_sdk` submodule directly (the `watch` field on `InfrahubGeneratorDefinitionConfig`), which carries its own tasks the same way the transform `watch:` work did for INFP-409.

### Out of Scope

- **Computed attributes ([IFC-1797](https://opsmill.atlassian.net/browse/IFC-1797))**: Already tracked separately.
- **Cross-branch fingerprint compare**: Deferred from INFP-409, not revisited here.
- **AST-based Python import analysis**: Explicitly rejected, same as INFP-409 - runtime/dynamic imports are invisible to static analysis and a missed one silently violates the correctness invariant. Cross-package dependencies are declared via `watch.files` instead.

## Risks

- **Per-member gate (FR-007)**: The interaction with `impacted_instances` in `_run_generator` is the one place needing careful thought. If subtle, it can absorb an extra day; if it is a clean predicate swap, it does not. Primary risk area — must preserve the never-under-run invariant.
- **Shared predicate refactor (FR-005)**: Touches code paths that artifacts also use; needs regression coverage so artifact behavior is unchanged (FR-013).

## Known Limitations

These are user-visible boundary conditions inherited from the shared INFP-409 machinery. They are not bugs and not out of scope - they are trade-offs the design has deliberately accepted and that carry over to generators unchanged.

- **`dependencies_complete` is never set `False` by code analysis for generators.** Unlike Jinja2 transforms - where the template walker sets it `False` on an unresolved dynamic include - generators are Python-only and AST import analysis is rejected (same as INFP-409), so no unresolved-reference detection exists. On the happy path a generator's closure is therefore always complete. The only thing that yields `dependencies_complete = False` is a closure-build failure at import time (git-enumeration error, unreadable file, or any isolated builder exception), which forces the safe regenerate-on-any-file-change fallback. The attribute is still load-bearing and written from the first import: the shared `_transform_changed` predicate reads it unconditionally, and it is the only signal that makes a failed-closure generator run-always instead of trusting an empty closure.
- **`watch:` is trusted, not verified.** A generator that imports from a sibling top-level package outside its own package directory is invisible to auto-detection; the user must declare it via `watch.files` (FR-014..FR-017). The system trusts that declaration - if the `watch.files` list does not actually cover the real dependency, the generator can still under-run. Verifying coverage would require knowing what runtime imports resolve to, which the system fundamentally cannot do; the mitigation is documentation and clear warning logs on non-matching entries.
- **`.infrahub.yml` whole-file conservatism.** The shared closure aggregator appends the manifest path to every closure it builds, so once generators route through it, any edit to `.infrahub.yml` re-runs every generator in that repository - even when the edit only touches an unrelated entry. This over-runs but is correct; per-entry granularity is a deferred improvement, identical to the artifact behavior in INFP-409.
- **Closure rebuilt on every import.** The integrator rebuilds each generator's closure (a `git ls_files` walk of its package directory) on every commit that re-imports it. Acceptable for this delivery; revisit only if benchmarks show a regression.
- **Edit-then-revert across branches over-runs.** When a source branch's generator-closure content is bit-identical to the destination branch after intermediate edits, the file diff is still non-empty and the generator runs. Resolving this needs the cross-branch fingerprint compare deferred from INFP-409 (out of scope).

## Assumptions

- All novel infrastructure from INFP-409 — closure builders, path canonicalizer, regeneration predicates, read-only-repo diff decoupling, watch-file union, and diagnostic logging — is already built and reusable. This work is replication and wiring, not invention. The `InfrahubWatchConfig` model already exists in the SDK and is reused as-is.
- `PythonClosure.build()` requires only `file_path` and `name`, both already present on `InfrahubGeneratorDefinitionConfig`, so it can consume the config without new input.
- The SDK is updated directly in the `python_sdk` submodule (the `watch` field on `InfrahubGeneratorDefinitionConfig`). Because the backend watch-union is already generic, adding the field is sufficient to make generator `watch:` functional; the remaining work is parsing tests, docs, and the changelog. The SDK change ships coordinated with the backend, the same way the transform `watch:` work shipped for INFP-409.
- The estimate is approximately 2 to 3 engineer-days plus review — slightly above the ticket's original 1.5-2.5 because the `watch:` field, its SDK tests, and its docs were promoted into scope; still well below INFP-409's roughly 5 days because all novel infrastructure already exists.
- Schema and GraphQL changes (FR-001) fall under the project's "ask first" boundary; they are pre-authorized by this ticket as a direct mirror of the INFP-409 attributes but must still be regenerated and committed per the code-generation pipeline.

## References

- **INFP-409**: original artifact regeneration trigger work.
- **Spec**: `dev/specs/infp-409-artifact-regen-triggers/` (see "Out of Scope: Generators").
- **INFP-607**: parent JPD idea — make generator and artifact execution incremental across all change scenarios.
