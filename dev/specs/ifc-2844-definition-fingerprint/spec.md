# Feature Specification: Definition Fingerprint Foundation

**Feature Branch**: `definition-fingerprint-ifc-2844`

**Created**: 2026-07-01

**Status**: Draft

**Input**: Jira epic IFC-2844 - "Introduce a `fingerprint` attribute on Transforms, GraphQL Queries, Artifact Definitions and Generators"

## Overview

Give each definition that produces output from a Git repository a single, branch-aware `fingerprint` attribute: a content hash of everything that actually determines its output. When the fingerprint is unchanged, the definition's output cannot have changed, so downstream work (computed-attribute recompute, artifact regeneration, generator runs) can later be skipped safely.

This feature delivers **only the foundation**: the schema fields, the fingerprint computation, and storing/overwriting the value on every repository import. It deliberately wires up **no consumer** and changes **no runtime behaviour on its own**. Consumers adopt the fingerprint under separate tickets (IFC-2804 computed attributes, IFC-2775 `.infrahub.yml` closure drop, artifact and generator regeneration gates).

### Non-negotiable invariant (inherited from INFP-409)

**Over-regeneration is acceptable; under-regeneration is not.** A definition that should regenerate but does not leaves stale data in production. Every fallback path (unknown/null fingerprint, no explicit `watch:` declaration) must default toward regeneration. This invariant governs every requirement and success criterion below.

## User Scenarios & Testing *(mandatory)*

The "users" of this foundation are (a) Infrahub developers building the consumer tickets that will react to fingerprint changes, and (b) end users who define Transforms, Artifact Definitions and Generators in Git repositories and whose no-op or reverting edits should stop causing needless downstream work once consumers adopt the signal. Each user story is an independently deliverable and testable slice of the layered fingerprint composition.

### User Story 1 - GraphQL Query fingerprint primitive (Priority: P1)

A `CoreGraphQLQuery` imported from a Git repository carries a `fingerprint` derived solely from its stored query text. This is the reusable primitive that every higher-level definition composes on.

**Why this priority**: Every other fingerprint (Transformation, Generator) depends on the query fingerprint. Without it, no other layer can be computed. It is the smallest slice that proves the schema field, the computation hook during import, and the SDK-over-GraphQL storage path all work end to end.

**Independent Test**: Import a repository containing a GraphQL query; confirm the query node has a non-null `fingerprint`. Re-import with no change and confirm the value is identical. Edit the query text and re-import; confirm the fingerprint changes. Edit an unrelated file and re-import; confirm the query fingerprint is unchanged.

**Acceptance Scenarios**:

1. **Given** a repository with a `CoreGraphQLQuery`, **When** the repository is imported, **Then** the query node has a non-null `fingerprint` attribute set through the standard GraphQL mutation path.
2. **Given** an already-imported query, **When** the repository is re-imported with the query text byte-identical, **Then** the `fingerprint` value is unchanged.
3. **Given** an already-imported query, **When** the query text changes and the repository is re-imported, **Then** the `fingerprint` value changes.
4. **Given** two imports whose query text differs only by attribute/field ordering that Infrahub normalises identically at import, **When** both are imported, **Then** their fingerprints match (fingerprint reflects stored, inlined query text, not raw bytes).

---

### User Story 2 - Transformation fingerprint (Priority: P1)

A `CoreTransformation` (inherited by `CoreTransformPython` and `CoreTransformJinja2`) carries a `fingerprint` that composes its connected query's fingerprint, its dependency closure, and its output-affecting manifest configuration. Its stability is governed by the transform's `watch:` declaration.

**Why this priority**: Transforms are the first real consumer target (transform-based computed attributes, IFC-2804) and exercise the full composition: query fingerprint reuse, closure hashing via `(repo_relative_path, git_blob_sha)` pairs, manifest-field inclusion, and the watch-driven commit-id placeholder that enforces the over-regenerate-never-under-regenerate invariant.

**Independent Test**: Import a Python and a Jinja2 transform; confirm each has a non-null `fingerprint`. Verify the value is stable across no-op re-import when `watch` is declared, changes when the connected query, a closure file's blob SHA, `class_name`/`convert_query_response` (Python) or `template_path` (Jinja2) changes, and is excluded from changing by `timeout` edits.

**Acceptance Scenarios**:

1. **Given** a Python transform with a connected query, **When** the repository is imported, **Then** its `fingerprint` incorporates the query's fingerprint, the sorted closure of `(path, blob_sha)` pairs, `class_name` and `convert_query_response`.
2. **Given** a Jinja2 transform, **When** the repository is imported, **Then** its `fingerprint` incorporates the query's fingerprint, the sorted closure, and `template_path`.
3. **Given** an imported transform, **When** only `timeout` changes in the manifest and the repository is re-imported, **Then** the `fingerprint` is unchanged.
4. **Given** an imported transform, **When** a file in its dependency closure changes content (new blob SHA), **Then** the `fingerprint` changes on re-import.
5. **Given** an imported transform whose connected query's fingerprint changes, **When** the repository is re-imported, **Then** the transform's `fingerprint` changes.
6. **Given** an imported transform with `watch: []` (so no commit-id placeholder), **When** the transform's own source file changes - the `.py` class file for Python, or the template file referenced by `template_path` for Jinja2 - **Then** the `fingerprint` changes, because the definition's own file is part of its dependency closure (its blob SHA is folded in independent of `watch:`).

---

### User Story 3 - Artifact Definition fingerprint (Priority: P2)

A `CoreArtifactDefinition` carries a `fingerprint` that composes its transformation's fingerprint with its own output-affecting fields and the identity of its target group.

**Why this priority**: Artifact regeneration is a primary consumer, but it builds directly on the Transformation fingerprint (US2) and cannot be delivered before it. It introduces the group-identity-not-membership rule that is critical to avoid regenerating every artifact on membership churn.

**Independent Test**: Import an artifact definition; confirm non-null `fingerprint`. Verify it changes when the transformation fingerprint, `parameters`, `content_type`, `artifact_name`, or the target group *identity* changes, and does **not** change when only group *membership* changes.

**Acceptance Scenarios**:

1. **Given** an artifact definition, **When** the repository is imported, **Then** its `fingerprint` incorporates the transformation's fingerprint, canonicalised `parameters`, `content_type`, `artifact_name`, and the target group's identity (related group id).
2. **Given** an imported artifact definition, **When** its target group is re-pointed to a different group, **Then** the `fingerprint` changes.
3. **Given** an imported artifact definition, **When** a member is added to or removed from its target group, **Then** the `fingerprint` is unchanged.

---

### User Story 4 - Generator Definition fingerprint (Priority: P2)

A `CoreGeneratorDefinition` carries a `fingerprint` composing its connected query's fingerprint, its dependency closure, its `parameters`, its target group's identity, and (when `watch` is not declared) a commit-id placeholder.

**Why this priority**: Generators are a consumer target, and the required `dependencies` / `dependencies_complete` / `watch:` fields on generator definitions are a prerequisite landed by PR #9700. This story reuses the same closure and watch machinery as US2 plus the group-identity rule from US3.

**Independent Test**: Import a generator definition; confirm non-null `fingerprint`. Verify it changes on query-fingerprint, closure, `parameters`, and group-identity changes, follows the same watch semantics as transforms, and is unaffected by group membership churn.

**Acceptance Scenarios**:

1. **Given** a generator definition, **When** the repository is imported, **Then** its `fingerprint` incorporates the connected query's fingerprint, the sorted closure of `(path, blob_sha)` pairs, canonicalised `parameters`, and the target group's identity.
2. **Given** an imported generator definition, **When** only its target group membership changes, **Then** the `fingerprint` is unchanged.
3. **Given** an imported generator definition with `watch` not declared, **When** any commit is made to the repository, **Then** the `fingerprint` changes on re-import (safe default, see US5).
4. **Given** an imported generator definition with `watch: []`, **When** only its `class_name` is changed to a different class in the same (unchanged) file, or its `convert_query_response` is toggled, **Then** the `fingerprint` changes (guards against under-regeneration once `.infrahub.yml` leaves the closure).

---

### User Story 5 - Watch-driven fingerprint stability (Priority: P1)

The `watch:` declaration in `.infrahub.yml` controls how far the fingerprint can be trusted. The configuration must distinguish three states: absent (`None`), explicitly empty (`[]`), and populated (`[files]`).

**Why this priority**: This is the crux of the non-negotiable invariant. For Python transforms and generators the auto-detected closure is only a package-directory floor and can silently miss dependencies, so a stable fingerprint without an explicit `watch:` would risk under-regeneration. Getting the three-state semantics right is what makes stable fingerprints safe; it must be correct in the first slice that produces a stable fingerprint.

**Independent Test**: For a transform/generator, set `watch` to each of the three states and confirm: absent -> fingerprint changes on every commit; empty list -> fingerprint stable across unrelated commits; populated -> declared files join the closure and the fingerprint changes only when they (or other closure inputs) change.

**Acceptance Scenarios**:

1. **Given** a definition whose `watch` is not declared (`None`), **When** any commit is made and the repository re-imported, **Then** a commit-id placeholder is folded into the fingerprint and the value changes.
2. **Given** a definition whose `watch` is an explicit empty list (`[]`), **When** an unrelated file changes and the repository is re-imported, **Then** the commit-id placeholder is omitted and the fingerprint is unchanged.
3. **Given** a definition whose `watch` lists specific files, **When** one of those files changes, **Then** the fingerprint changes; **When** an undeclared, non-closure file changes, **Then** the fingerprint is unchanged.
4. **Given** the watch configuration, **When** it is loaded, **Then** absent and explicitly-empty are represented as distinct states (`None` vs `[]`).

---

### Edge Cases

- **Pre-feature nodes**: definitions imported before this feature (or never re-imported afterward) have a null `fingerprint`. Consumers must treat null as "unknown -> regenerate". This foundation only guarantees the field exists and is nullable; it does not backfill.
- **Edit-then-revert**: content changed and then reverted to identical bytes must yield an identical fingerprint (net-zero change), because the fingerprint is content-derived.
- **Comment-only `.infrahub.yml` edit**: for a definition with a declared `watch`, editing only a comment or an unrelated section of `.infrahub.yml` must not change the fingerprint (this is what later lets IFC-2775 drop `.infrahub.yml` from the closure). Note: while `watch` is absent, the folded commit id still changes the fingerprint - that is the safe default, not a regression.
- **User desync via API**: because the attribute is writable (not `read_only`), a user could set `fingerprint` directly through the API and desync it. This risk is accepted and is no worse than other importer-managed fields; the next import overwrites it.
- **Missing/omitted output-affecting field**: if a future output-affecting manifest field is added but not folded into the relevant fingerprint, editing only that field would leave the fingerprint stable and cause under-regeneration. The completeness condition (FR-021) guards against this. This is not hypothetical: the source epic's generator composition omitted `class_name` and `convert_query_response`, which FR-012a restores.
- **Non-deterministic serialisation**: closures and `parameters` must be canonicalised (sorted closure pairs, canonical JSON) so that logically-identical inputs always hash identically regardless of ordering.

## Requirements *(mandatory)*

### Functional Requirements

#### Schema fields

- **FR-001**: The system MUST add a `fingerprint` attribute to `CoreGraphQLQuery`, `CoreTransformation` (generic, inherited by `CoreTransformPython` and `CoreTransformJinja2`), `CoreArtifactDefinition`, and `CoreGeneratorDefinition`.
- **FR-002**: The `fingerprint` attribute MUST be of kind `Text` and optional; a null value MUST be permitted and MUST mean "pre-feature node, never re-imported" (treated by consumers as "unknown -> regenerate").
- **FR-003**: The `fingerprint` attribute MUST use `BranchSupportType.AWARE`, so the value is per-branch and participates in branch diffs, rebases and merges like the definitions it sits on.
- **FR-004**: The `fingerprint` attribute MUST NOT be `read_only`; it MUST be writable through the standard mutation path so the importer (a Prefect worker holding no database access) can set it via the SDK over GraphQL.

#### Computation and storage

- **FR-005**: The system MUST compute each fingerprint during repository import, composed over the existing dependency-closure build machinery.
- **FR-006**: The system MUST write the fingerprint through the standard mutation path (SDK over GraphQL), NOT a low-level direct-DB write, so that (a) it works when the importing worker has no DB access, and (b) the write goes through the normal node-update pipeline and emits the attribute-change event and branch diff that consumers rely on.
- **FR-007**: The system MUST overwrite the fingerprint on every import. It MUST NOT compare against or reason about the prior value; change detection is a normal branch diff performed by consumers at consume time.

#### Fingerprint composition

- **FR-008**: `CoreGraphQLQuery.fingerprint` MUST be `hash(query_text)`, where `query_text` is the stored, fragment-inlined `query` attribute.
- **FR-009**: `CoreTransformation.fingerprint` MUST hash: the connected query's fingerprint; the dependency closure as a sorted list of `(repo_relative_path, git_blob_sha)` pairs over the stored `dependencies`; the non-file output-affecting manifest config (`class_name` and `convert_query_response` for Python, `template_path` for Jinja2); and a commit-id placeholder if and only if `watch` is `None`.
- **FR-009a** (definition's own source file): The dependency closure MUST include the definition's own source file, and its blob SHA MUST therefore be part of the fingerprint, independent of any `watch:` declaration. For a Python transform this is the `.py` file that defines the class (the closure is the git-tracked contents of the directory containing it); for a Jinja2 transform this is the template file referenced by `template_path` (seeded into the closure and walked transitively for `include`/`import`/`extends`). Editing the transform's own logic or template MUST change its fingerprint even when `watch` is `[]`.
- **FR-009b** (blob-SHA resolution): The stored `dependencies` is a list of canonical repo-relative paths only; it does NOT store blob SHAs. Fingerprint computation MUST resolve the current git blob SHA for each closure path at import time and hash the `(path, blob_sha)` pairs. This is a read of git metadata, not of file contents.
- **FR-010**: The `timeout` field MUST be excluded from the transformation fingerprint (it affects execution limits, not output).
- **FR-011**: `CoreArtifactDefinition.fingerprint` MUST hash: the transformation's fingerprint; `parameters` (canonicalised JSON); `content_type`; `artifact_name` (the name template); and the target group's identity (the related group id).
- **FR-012**: `CoreGeneratorDefinition.fingerprint` MUST hash: the connected query's fingerprint; the dependency closure as sorted `(path, blob_sha)` pairs; `parameters`; `class_name`; `convert_query_response`; the target group's identity; and a commit-id placeholder if and only if `watch` is `None`. The closure MUST include the generator's own `.py` definition file (per FR-009a), so its blob SHA is part of the fingerprint independent of `watch:`.
- **FR-012a** (generator completeness correction): `class_name` and `convert_query_response` MUST be in the generator fingerprint even though the source epic's composition list omits them. Both are output-affecting manifest fields on the generator definition (`class_name` selects which class in the file runs; `convert_query_response` changes how the query response is delivered to the generator). They are not captured by the closure blob SHAs (a `class_name` change re-points to a different class in the same, unchanged file). Omitting them would satisfy the letter of the epic list but violate the completeness condition (FR-021) and cause under-regeneration once `.infrahub.yml` leaves the closure (IFC-2775). Execution-control fields (`execute_in_proposed_change`, `execute_after_merge`) are deliberately excluded because they affect when/whether the generator runs, not its output - the same rationale as excluding `timeout` from transformations (FR-010).
- **FR-013**: Group **identity** MUST be included in artifact-definition and generator-definition fingerprints (re-pointing to a different group MUST invalidate the fingerprint); group **membership** MUST be excluded (adding/removing a member MUST NOT change the fingerprint). Membership churn stays on the existing per-member resolution path.
- **FR-014**: The dependency closure and all structured inputs (e.g. `parameters`) MUST be canonicalised deterministically (sorted closure pairs, canonical JSON) so that logically-identical inputs always produce identical fingerprints regardless of ordering.
- **FR-015**: Fingerprint composition MUST be layered so each level reuses the level below (query -> transformation -> artifact definition; query -> generator definition).
- **FR-015a** (consistent snapshot): Within a single import, a higher-level fingerprint MUST compose the freshly-computed lower-level fingerprint from that same import, not a previously-stored value. Otherwise a change to a query or transformation in an import would not propagate into the dependent artifact-definition fingerprint until a later import, causing a one-import under-regeneration lag on the dependent definition (a violation of the non-negotiable invariant). This implies computing fingerprints in dependency order per import (queries, then transformations, then artifact definitions).
- **FR-015b** (non-output fields excluded): Purely descriptive or execution-control fields MUST NOT be folded into any fingerprint. This includes `description` on transformations, `timeout` (FR-010), and `execute_in_proposed_change` / `execute_after_merge` on generators (FR-012a). Only output-affecting inputs are hashed.

#### Watch semantics

- **FR-016**: When `watch` is not declared (`None`), the system MUST fold the current commit id into the fingerprint, so the fingerprint changes on every commit (the safe default that reverts to legacy over-regeneration).
- **FR-017**: When `watch` is an explicit empty list (`[]`), the system MUST omit the commit-id placeholder, producing a stable, precise fingerprint (user opt-in asserting no dependencies beyond the auto-detected closure).
- **FR-018**: When `watch` lists specific files, the system MUST extend the closure with those files, treat the closure as complete, and produce a stable, precise fingerprint.
- **FR-019**: The watch configuration MUST be able to represent absent (`None`) and explicitly-empty (`[]`) as distinct states, and the fingerprint computation MUST branch on that distinction (absent -> fold commit id; explicitly-empty -> do not). NOTE: today the closure builder treats "watch absent" and "watch present but with no files" identically (both skip closure expansion), so no consumer currently distinguishes them. This feature must introduce that distinction for fingerprint purposes. The current config shape is an object (`watch:` with a `files` list), not a bare list; the epic's `watch: []` / `watch: [files]` shorthand maps onto "the `watch:` key is present" (explicit, so stable) versus absent (so unstable). Any change to the config model or its parsing to make the two states distinguishable is in scope.

#### Scope guards and completeness

- **FR-020**: This feature MUST NOT change any consumer: no trigger rewired, no regeneration/recompute gate changed, nothing skipped as a result of this feature alone. Existing regeneration behaviour MUST be observably unchanged.
- **FR-021** (Completeness condition): Every output-affecting field that originates in the manifest MUST be enumerated in the relevant fingerprint. Any future output-affecting field MUST be added to the relevant fingerprint. (This is what makes the later `.infrahub.yml` closure drop safe.)
- **FR-022**: `.infrahub.yml` MUST remain in the dependency closure in this feature; removing it is the IFC-2775 consumer change and is out of scope here.

#### Generated files

- **FR-023**: The system MUST regenerate and commit all dependent generated files affected by the schema additions: `backend/infrahub/core/protocols.py`, the generated schema definitions under `backend/infrahub/core/schema/generated/`, the GraphQL schema export (`schema/schema.graphql`), the OpenAPI export (`schema/openapi.json`), and the frontend GraphQL types. Regeneration MUST use the offline regeneration tasks, and CI's generated-file/doc validation MUST pass.

### Key Entities

- **fingerprint attribute**: a nullable, branch-aware `Text` attribute holding a content hash of a definition's output-affecting inputs; writable (not read-only); overwritten every import.
- **CoreGraphQLQuery**: holds the inlined query text; source of the primitive fingerprint.
- **CoreTransformation / CoreTransformPython / CoreTransformJinja2**: transformations whose fingerprint composes the query fingerprint, closure, and manifest config.
- **CoreArtifactDefinition**: composes a transformation fingerprint with `parameters`, `content_type`, `artifact_name`, and target-group identity.
- **CoreGeneratorDefinition**: composes a query fingerprint with closure, `parameters`, `class_name`, `convert_query_response`, and target-group identity (requires PR #9700 fields). Execution-control fields (`execute_in_proposed_change`, `execute_after_merge`) are excluded.
- **Dependency closure**: the set of canonical repo-relative paths describing files that affect a definition's output; built during import (INFP-409), always including the definition's own source file (Python `.py`, Jinja2 template, generator `.py`), and extended by `watch:` files. Blob SHAs are not stored on the closure; they are resolved at fingerprint time to form the hashed `(path, blob_sha)` pairs.
- **watch configuration**: the `.infrahub.yml` declaration governing fingerprint trust; three states - absent (`None`), explicit empty (`[]`), populated (`[files]`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a repository import, 100% of imported `CoreGraphQLQuery`, `CoreTransformation`, `CoreArtifactDefinition`, and `CoreGeneratorDefinition` nodes have a non-null `fingerprint`.
- **SC-002**: Re-importing a repository with no content changes produces zero fingerprint changes for all four definition kinds whose `watch` is declared (`[]` or populated) - measurable as an empty branch diff on the `fingerprint` attribute.
- **SC-003**: Any change to an output-affecting input (query text, a closure file's blob SHA including the definition's own source file, `class_name`/`convert_query_response` for Python transforms and generators, `template_path` for Jinja2, `parameters`, `content_type`, `artifact_name`, or target-group identity) changes the corresponding fingerprint 100% of the time.
- **SC-004**: A change followed by its exact revert yields a net-zero fingerprint change (identical value before and after).
- **SC-005**: For a definition with a declared `watch`, a comment-only or unrelated `.infrahub.yml` edit yields zero fingerprint change.
- **SC-006**: For a definition whose `watch` is absent, every commit changes the fingerprint (no under-regeneration is possible from a stale stable value).
- **SC-007**: Group membership churn (add/remove one member) yields zero fingerprint change on affected artifact/generator definitions, while re-pointing to a different group changes it 100% of the time.
- **SC-008**: No existing consumer behaviour changes: the regeneration/recompute triggers that fire today fire identically after this feature (verified by existing regression tests remaining green with no trigger-count changes).
- **SC-009**: CI's generated-file and generated-doc validation passes with all regenerated artifacts committed (no stale generated files).
- **SC-010**: The `fingerprint` value participates correctly in branch operations: it appears in branch diffs and survives rebase/merge as a normal branch-aware attribute.

## Assumptions

- **PR #9700 has landed** (visible as a merge commit on `develop`), so `CoreGeneratorDefinition` already exposes the `dependencies` / `dependencies_complete` / `watch:` fields the generator fingerprint depends on. If any of these are missing, US4 is blocked until they land.
- **Fragments are inlined at import time**, so `CoreGraphQLQuery.query` is self-contained and no separate fragment resolution is needed for the query fingerprint.
- **The dependency closure is already built during import** (INFP-409) and already includes the package-directory floor plus any `watch:` files; the fingerprint composes over it rather than rebuilding it.
- **Hash function**: a stable, collision-resistant hash producing a deterministic textual digest is used (reasonable default: SHA-256 hex digest). The exact algorithm is an implementation detail provided it is deterministic and stable across processes and Infrahub versions; changing the algorithm later would invalidate all stored fingerprints and force a full re-import, which is acceptable over-regeneration.
- **Git blob SHAs are available** for every closure file at import time, so file contents never need to be read to hash the closure.
- **No backfill/migration** of fingerprints for pre-existing nodes is required; null is the correct value until the next import, and consumers treat null as "regenerate".
- **Per repo convention**, no Jira/spec/issue IDs appear in source comments, docstrings, or test names; those belong in the commit message, PR description, and changelog fragment.
- **Consumers are out of scope**: initial computation on create, selective recompute on update, and Prefect-automation teardown on delete are all consumer concerns handled in follow-up tickets (IFC-2804, IFC-2775, and the artifact/generator regeneration-gate tickets).
- **Deliberate deviations from the epic's composition list** (flagged for reviewer confirmation): (1) FR-012a adds `class_name` and `convert_query_response` to the generator fingerprint, which the epic's bullet list omits, to satisfy the epic's own completeness condition. (2) FR-009a/FR-012 state explicitly that the definition's own source file is in the closure (the epic only implied it via "package-directory floor"). Both are conservative (they can only cause more regeneration, never less) and align with the non-negotiable invariant; neither contradicts the epic's intent.
- **Watch config shape**: the `watch:` declaration is currently an object with a `files` list (`InfrahubWatchConfig`), not a bare list. The epic's `watch: []`/`watch: [files]` notation is shorthand. The absent-vs-explicit-empty distinction the epic requires is not currently observed by any consumer (the closure builder collapses them), so this feature introduces it for fingerprint purposes; the exact config representation is an implementation choice provided both states are distinguishable.
