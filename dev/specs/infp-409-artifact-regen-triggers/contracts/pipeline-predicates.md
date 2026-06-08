# Contract: Pipeline-time regeneration predicates

Three Python predicates replace the two call sites of the current `has_file_modifications` gate. They take in-memory pipeline models (already populated by `_gather_artifact_definitions` and `_gather_repository_repository_diffs`) and return booleans. No new IO, no new Cypher.

## Predicates

### `_query_changed(definition, diff_summary) -> bool`

**Signature**:

```python
def _query_changed(
    definition: ProposedChangeArtifactDefinition,
    diff_summary: list[NodeDiff],
) -> bool: ...
```

**Returns** `True` if and only if `diff_summary` contains an entry whose `id` equals `definition.query_id`.

**Why this works**: `CoreGraphQLQuery.query` is updated by the SDK's `import_all_graphql_query`, which inlines every fragment body before persisting (`render_query_with_fragments`). A change to the primary `.gql` file or any transitively-referenced fragment produces a different stored query text, which surfaces as a node modification in `diff_summary`. No separate fragment-tracking is needed.

**Diagnostic log (FR-022)**: when `True`, log via the Prefect logger:

```text
Definition <name> (<id>): GraphQL query <query_name> (<query_id>) was modified — all artifacts of this definition will regenerate.
```

### `_definition_changed(definition, diff_summary) -> bool`

**Signature**:

```python
def _definition_changed(
    definition: ProposedChangeArtifactDefinition,
    diff_summary: list[NodeDiff],
) -> bool: ...
```

**Returns** `True` if and only if `diff_summary` contains an entry whose `id` equals `definition.node_id` (the `CoreArtifactDefinition` node id).

**Why this works**: A change to the definition's `targets` relationship, `transformation` relationship, `query` relationship, or any attribute on the definition produces a node modification in `diff_summary`. The predicate covers all such cases uniformly.

**Diagnostic log (FR-022)**: when `True`, log the specific attribute or relationship that changed (read from the matching `diff_summary` entry's per-field detail).

### `_transform_changed(definition, repo_diff) -> bool`

**Signature**:

```python
def _transform_changed(
    definition: ProposedChangeArtifactDefinition,
    repo_diff: ProposedChangeRepository,
) -> bool: ...
```

**Behavior**:

| `definition.dependencies` | `definition.dependencies_complete` | Behavior |
|---|---|---|
| `None` | `None` | Legacy node, never re-imported under Stage 2. **Fallback**: return `True` if and only if `repo_diff` has any file modifications (FR-024). |
| any | `False` | Closure is incomplete (e.g. unresolved Jinja2 include with no `watch:`, or closure-builder failure). **Fallback**: return `True` if and only if `repo_diff` has any file modifications (FR-013, FR-023, FR-024). |
| `[]` | `True` | Transform genuinely depends on nothing in the repo. Return `False` regardless of `repo_diff`. |
| non-empty | `True` | Compute set intersection: `True` if and only if any file in `dependencies` matches any file in `repo_diff.files_added ∪ files_changed ∪ files_removed`. |

Paths on both sides are canonicalized via the shared canonicalizer before comparison.

**Diagnostic log (FR-022, FR-023)**: when `True`, log the intersecting file(s) or the fallback reason:

```text
Definition <name>: file <path> changed and is in this transform's dependency closure — all artifacts will regenerate.
```

```text
Definition <name>: transform dependency closure is incomplete (dependencies_complete=False) — falling back to regenerate-on-any-file-change. Unresolved references: [...].
```

```text
Definition <name>: transform was imported before this feature deployed (dependencies=null) — falling back to regenerate-on-any-file-change. The next re-import of this transform will populate its dependency closure.
```

## Call-site replacement matrix

| Call site (today) | Replacement (Stage 1) | Replacement (Stage 2) |
|---|---|---|
| `refresh_artifacts` selection gate `FILE_CHANGES` flag (`tasks.py:1363–1382`) | `_query_changed(definition, diff_summary) OR _definition_changed(definition, diff_summary)` ORed with existing `MODIFIED_KINDS` | additionally OR `_transform_changed(definition, repo_diff_for_this_definition)`; remove the `has_file_modifications` short-circuit |
| `validate_artifacts_generation` per-definition fan-out (`tasks.py:805–807`) — sets `managed_branch = True` and short-circuits `_should_render_artifact` | conditional flip: only flip `managed_branch` when `_query_changed OR _definition_changed` | additionally flip when `_transform_changed`; the old `has_file_modifications` short-circuit can be removed |
| `branch_diff` population gated on `source_branch_sync_with_git` (today) | unchanged in Stage 1 | per FR-017–FR-020, compute per-repo diffs regardless of `sync_with_git`; `CoreReadOnlyRepository` uses pinned-commit diff, `CoreRepository` uses tracked-branch-tip diff |

## Stage 1 / Stage 2 interim behavior

If Stage 1 ships before Stage 2:

- `_query_changed` and `_definition_changed` are live.
- `_transform_changed` is not in the gate yet.
- The legacy `has_file_modifications` short-circuit remains as a third OR-clause for the selection gate, so that transform-file edits still trigger regeneration (preserving today's behavior — no new failure mode).

When Stage 2 lands, `_transform_changed` replaces the residual `has_file_modifications` clause, and the legacy short-circuit is removed.

## Inputs already in the pipeline

| Input | Source | Already plumbed? |
|---|---|---|
| `definition.query_id` | `GATHER_ARTIFACT_DEFINITIONS` selects `query { node { id } }` | yes |
| `definition.node_id` | id of the `CoreArtifactDefinition` row in the gather query | yes |
| `definition.dependencies` | new — `transformation { node { dependencies { value } } }` | Stage 2 plumbing |
| `definition.dependencies_complete` | new — `transformation { node { dependencies_complete { value } } }` | Stage 2 plumbing |
| `diff_summary` | already gathered for the data-change path | yes |
| `repo_diff` per definition | `_gather_repository_repository_diffs`; keyed by the transform's repository id | yes (mapping from definition → repo via `transformation.repository`) |

## Out of contract

These are explicitly *not* part of the pipeline-predicate contract:

- Cross-branch fingerprint compare (Phase 3, deferred).
- Per-entry manifest hashing (deferred).
- AST-precise Python import analysis (rejected — Decision 6).
- Verifying that a user's `watch.files` covers their dynamic references (impossible by construction — see spec Out of Scope).

## Component design (per `dev/rules/backend-component-design.md`)

The three predicates are pure functions over already-typed input models. They satisfy the rule by passing the work payload (the `definition` and the relevant diff) as method arguments and not holding state. There is no second implementation, so no Protocol/ABC is introduced yet.

The closure builder (`Jinja2Closure`, `PythonClosure`) is a different component — a `ClosureBuilder` Protocol with two implementations selected at wiring time by the integrator. Constructor injects long-lived collaborators (path canonicalizer, logger); entry method takes the transform config + worktree path and returns a `ClosureResult` (see data-model.md §3). That component lives in `backend/infrahub/git/closure_builder/` and is *not* part of this predicate contract — it is documented here only for the closure-result shape that flows into `_transform_changed`.
