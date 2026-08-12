# Contract: Structural Protocol + predicate / gate reuse for generators

The three shipped INFP-409 predicates already encode the regeneration logic. This feature does not write new predicates; it (a) introduces a structural `Protocol` both definition models satisfy so the existing predicates accept generators, (b) parametrizes the diagnostic wording, and (c) swaps the two blunt generator gates to call the predicates. This contract pins the Protocol shape, the predicate behavior as seen by the generator caller, and the call-site replacement matrix.

## The structural Protocol

```python
class RegenerationDefinition(Protocol):
    definition_id: str
    definition_name: str
    query_id: str
    query_name: str
    dependencies: list[str] | None
    dependencies_complete: bool | None

    @property
    def source_noun(self) -> str: ...      # "transform" (artifact) | "generator source" (generator)
    @property
    def instance_noun(self) -> str: ...     # "artifacts" (artifact) | "instances" (generator)
```

The predicates are retyped from `ProposedChangeArtifactDefinition` to `RegenerationDefinition`. Both `ProposedChangeArtifactDefinition` and `ProposedChangeGeneratorDefinition` satisfy it structurally; neither gains a new base class.

## Predicate behavior (generator caller view)

### `_query_changed(definition, diff_summary) -> PredicateOutcome`

`matched = True` iff `diff_summary` contains an entry whose `id == definition.query_id` with a triggering action (`ADDED` / `UPDATED`). The SDK inlines fragment bodies into the stored query, so any `.gql` or fragment edit surfaces as one `CoreGraphQLQuery` node modification — an id match is sufficient. A generator whose query peer cannot be resolved simply never matches here; the other signals still cover it (never-under-run is preserved by `_transform_changed`).

**Reason (matched)**: `Definition <definition_name> (<definition_id>): GraphQL query <query_name> (<query_id>) was modified - all <instance_noun> of this definition will <run|regenerate>.`

### `_definition_changed(definition, diff_summary) -> PredicateOutcome`

`matched = True` iff `diff_summary` contains an entry whose `id == definition.definition_id` with a triggering action. Any attribute change or relationship repoint (`targets`, `query`, etc.) on the definition surfaces as a modification of its own node id.

**Reason (matched)**: `Definition <definition_name> (<definition_id>): definition node was modified (<changed_fields>) - all <instance_noun> of this definition will <run|regenerate>.`

### `_transform_changed(definition, repo_diff) -> PredicateOutcome`

| `dependencies` | `dependencies_complete` | Behavior |
|---|---|---|
| `None` | `None` | Legacy generator, never re-imported. **Fallback**: `matched = repo_diff.has_modifications` (FR-009). |
| any | not `True` | Closure incomplete (build failure). **Fallback**: `matched = repo_diff.has_modifications`. |
| `[]` | `True` | Genuinely depends on nothing else. `matched = False`. |
| non-empty | `True` | Set intersection of canonicalized `dependencies` with canonicalized `repo_diff.files_added ∪ files_changed ∪ files_removed`. `matched = True` iff non-empty. |

**Reason (precise match)**: `Definition <definition_name>: file <path(s)> changed and is in this <source_noun>'s dependency closure - all <instance_noun> will <run|regenerate>.`
**Reason (legacy fallback)**: names `dependencies=null` and the self-heal-on-re-import path.
**Reason (incomplete fallback)**: names `dependencies_complete=False`.

All reason strings are emitted by the caller via the existing `PredicateOutcome.reason` → `log.info` mechanism. **FR-013 regression guard**: with `source_noun = "transform"` and `instance_noun = "artifacts"`, every artifact reason string must be byte-for-byte what it is today.

## Call-site replacement matrix

| Call site (today) | Replacement |
|---|---|
| `run_generators` — `DefinitionSelect.FILE_CHANGES` flag set from `source_branch_sync_with_git AND branch_diff.has_file_modifications` | `_query_changed OR _definition_changed`, ORed with `_transform_changed(repo_diff_for_definition)` via `_repo_diff_or_none(...)`; `MODIFIED_KINDS` clause unchanged; log each `reason` at INFO (FR-006) |
| `request_generator_definition_check` — `managed_branch = model.source_branch_sync_with_git` passed to `_run_generator` | `managed_branch = (_query_changed OR _definition_changed OR _transform_changed(repo_diff)).matched`; everything else in `_run_generator` unchanged (FR-007) |
| `MODIFIED_KINDS` clause in `run_generators` | unchanged (data-change path already correct, FR / spec Edge Cases) |
| per-repo diff gated on `sync_with_git` | already decoupled by INFP-409 US5; verified, not changed (FR-008) |

## Never-under-run proof for the per-member gate (FR-007)

`_run_generator(instance_id, managed_branch, impacted_instances)` returns `True` when `not instance_id or managed_branch`, else `instance_id in impacted_instances`. After the swap:

- **New member** (`instance_id is None`) → runs regardless of `managed_branch` (category 2 preserved).
- **Existing member whose data changed** → in `impacted_instances` → runs regardless of `managed_branch` (category 1 preserved).
- **Existing member, closure/query/definition changed** → `managed_branch = True` → all existing instances run (category 3, the intended new precision).
- **Existing member, nothing relevant changed** → `managed_branch = False`, not impacted → correctly skipped (the win).
- **Legacy / failed closure** → `_transform_changed` falls back to `repo_diff.has_modifications`, so `managed_branch = True` on any file change → never under-runs.

## Inputs already in the pipeline

| Input | Source | Already plumbed? |
|---|---|---|
| `definition.query_id` | `generator.query.peer.id` (peer prefetched for `query_name`) | added by FR-004 (peer already loaded) |
| `definition.definition_id` | gathered `CoreGeneratorDefinition` id | yes |
| `definition.dependencies` / `dependencies_complete` | new node attributes | added by FR-001 + FR-004 |
| `diff_summary` | already gathered for the data-change path | yes |
| `repo_diff` per definition | `_repo_diff_or_none(branch_diff, repository_id)` | yes |

## Out of contract

- New predicate logic (none — reused).
- Cross-branch fingerprint compare (deferred).
- AST-precise Python import analysis (rejected).
- Verifying a user's `watch.files` covers real runtime imports (impossible by construction).
