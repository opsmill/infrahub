# Phase 1 Data Model

This file enumerates every entity touched by the feature: schema attributes added to the graph, in-memory models extended on the pipeline side, the SDK repository-config submodel that carries the `watch:` field, and the canonicalized-path form that ties them together.

## 1. `CoreTransformation` — schema additions (Stage 2)

Two new attributes added to the generic `CoreTransformation` schema (`backend/infrahub/core/schema/definitions/core/transform.py`). Both specializations (`CoreTransformJinja2`, `CoreTransformPython`) inherit them.

| Attribute | Kind | Optional | Default | Purpose |
|---|---|---|---|---|
| `dependencies` | `List` of `Text` | yes | `null` (sentinel) | Canonical repo-relative paths whose contents are inputs to this transform's output. Populated at git-import time by the closure builder. `null` means "no information yet" — pipeline falls back to legacy gate for this transform. `[]` is a legitimate value (transform genuinely depends on nothing else in the repo). |
| `dependencies_complete` | `Boolean` | yes | `null` | `true` when the closure can be trusted at pipeline time. `false` when auto-detection found unresolved references (e.g. `{% include some_var %}`) and the user has not declared a covering `watch:`. `null` only in the pre-feature state (legacy nodes); pipeline treats `null` the same as `dependencies is null`. |

### Validation rules

- `dependencies` entries are strings in the canonical path form (see §4 below). Validation at write time: each entry MUST match the canonical normalizer's fixed point (idempotent).
- `dependencies_complete` is a free boolean — no cross-field validation against `dependencies`. The completeness semantics are upheld by the closure builder, not by the schema layer.

### State transitions

- **Pre-feature → Stage 2 deployed, transform not yet re-imported:** `dependencies = null`, `dependencies_complete = null`. Pipeline falls back to today's behavior for this transform.
- **First re-import under Stage 2 code:** Closure builder populates `dependencies` (possibly `[]`) and sets `dependencies_complete = True | False` per Decision 5 / 6 / 9 in research.md. The transform now participates in the precise gate on the next proposed change.
- **Closure-builder failure on re-import:** `dependencies = []` (best-effort partial closure if Jinja2 walk produced one) and `dependencies_complete = False`. Pipeline falls back to legacy gate, preserving the safety invariant.
- **User adds non-empty `watch.files`:** Closure builder unions `watch.files` with the auto-detected closure; `dependencies_complete = True` (trusting user assertion per FR-014).

### Branch semantics

Both attributes are `BranchSupportType.AWARE` (inherited from `CoreTransformation`). Different branches can hold different closures for the same transform, which is the correct behavior — a transform's source can differ between branches.

## 2. `ProposedChangeArtifactDefinition` — model extensions (Stage 1 + Stage 2)

In-memory Pydantic model (`backend/infrahub/message_bus/types.py`) used in the proposed-change pipeline. Already carries `query_id`. Stage 2 adds two fields plumbed in from the gather query.

| Field | Type | Stage | Source |
|---|---|---|---|
| `query_id` | `str` | already present | `CoreGraphQLQuery` node id |
| `dependencies` | `list[str] \| None` | Stage 2 | `transformation { node { dependencies { value } } }` in `GATHER_ARTIFACT_DEFINITIONS` |
| `dependencies_complete` | `bool \| None` | Stage 2 | `transformation { node { dependencies_complete { value } } }` |

`query_id` is already used by the data-change path; Stage 1 starts using it for the selection-gate predicate. Stage 2 adds the two new fields.

### Validation rules

- `dependencies` is parsed verbatim from the graph (no re-canonicalization at read time — paths were canonicalized at write time and the normalizer is idempotent).
- `dependencies_complete` is a tri-state from the pipeline's perspective: `True`, `False`, or `None`. The predicate treats `None` and `False` identically (both fall back to legacy gate), but they are kept distinct so logs can identify "never imported" vs. "imported but incomplete".

## 3. `ClosureResult` — closure builder return shape (Stage 2)

New frozen dataclass in `backend/infrahub/git/closure_builder/result.py`.

```python
@dataclass(frozen=True, kw_only=True, slots=True)
class ClosureResult:
    dependencies: tuple[str, ...]       # canonical paths, deterministic order
    complete: bool                      # dependencies_complete value to persist
    unresolved: tuple[UnresolvedRef, ...]  # for diagnostic logging only

@dataclass(frozen=True, kw_only=True, slots=True)
class UnresolvedRef:
    file: str                           # canonical path to the file containing the unresolved reference
    location: str                       # human-readable site (e.g. "line 42" or "include expression at line 42")
```

### Invariants

- `dependencies` is sorted lexicographically before being returned, so two builds of the same closure produce byte-identical attribute values (avoids spurious node modifications in `diff_summary`).
- `unresolved` is non-empty implies `complete is False` *unless* the caller is going to union with a non-empty `watch.files` (FR-014). The closure builder returns the auto-detected `complete` value; the integrator computes the final stored `complete` after the union.

## 4. Canonical path form

Defined and enforced in `backend/infrahub/git/closure_builder/canonicalizer.py`. The single shared helper.

| Property | Value |
|---|---|
| Base | repo-relative (never absolute) |
| Separator | POSIX `/` (forward slashes), even when the worktree was checked out with backslashes |
| Leading dot-slash | stripped (`./utils` → `utils`) |
| Trailing slash | stripped (`utils/` → `utils` for storage; the closure builder expands directory entries to their contents before storage) |
| Symlinks | not resolved — the canonical path is what git sees |
| Case | preserved (no case-fold) |
| Encoding | utf-8 |

### Applied symmetrically

- **Write side (closure builder):** Every path entering `dependencies` (auto-detected closure, `watch.files` directory expansions, `.infrahub.yml` manifest path) is canonicalized before storage.
- **Read side (pipeline predicate):** Every path from `ProposedChangeRepository.files_added / changed / removed` is canonicalized before the set intersection.

The canonicalizer is idempotent: `canonicalize(canonicalize(p)) == canonicalize(p)`. Used as a schema-level validator on `dependencies` writes.

## 5. SDK `InfrahubWatchConfig` (Stage 2)

New Pydantic submodel in `python_sdk/infrahub_sdk/schema/repository.py`. Embedded on `InfrahubJinja2TransformConfig` and `InfrahubPythonTransformConfig` as an optional `watch: InfrahubWatchConfig | None = None` field.

```python
class InfrahubWatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[str] = Field(default_factory=list, description="Additional files or directories that contribute to the transform's rendered output. Directory entries match recursively.")
```

### Validation rules

- `files` entries are strings (raw user input). The SDK does not canonicalize them — the backend integrator is the canonicalization authority (Decision 4 in research.md). This means `utils/`, `./utils`, and `utils` all flow through the SDK identically and are normalized server-side.
- `extra="forbid"` rejects unknown keys at parse time, so a typo like `watch: { fles: [...] }` errors clearly.
- The list form (`watch: [a, b]`) is rejected by Pydantic's type-checking — only the object form is accepted (FR-011).

### Future keys

`InfrahubWatchConfig` is shaped to accept additional sibling keys later (e.g. `strict: bool`, `exclude: list[str]`) without migration. None are added in this feature.

## 6. Repository file diff — `ProposedChangeRepository`

Existing model (`backend/infrahub/message_bus/types.py`) gains no new fields, but the *population* of `files_added`, `files_changed`, `files_removed` changes (per FR-017–FR-020):

| Repository kind | Diff source | Conditioning |
|---|---|---|
| `CoreRepository` | `git diff <destination_branch_tip>..<source_branch_tip>` on the tracked Git branches | Always computed; not gated on `sync_with_git`. When `sync_with_git = False`, the tracked commits don't move and the diff is naturally empty. |
| `CoreReadOnlyRepository` | `git diff <destination_pinned_commit>..<source_pinned_commit>` between the pinned commits on the source vs destination Infrahub branches | Always computed; not gated on `sync_with_git`. |

The diff is keyed by `repository_id`. Per-repository, per-branch-pair. Paths returned are in git's native form and are canonicalized at the pipeline predicate before the intersection.

## 7. `.infrahub.yml` — manifest path entry

Not a new entity. The path to the repo's `.infrahub.yml` is computed by the integrator (which already reads the file) and appended to every transform's `dependencies` in that repo. The canonical form is `.infrahub.yml` (root-level file). No nesting.

## 8. Pipeline-time predicate inputs

The three predicates (`_query_changed`, `_definition_changed`, `_transform_changed`) operate on the data above. Inputs:

| Predicate | Inputs |
|---|---|
| `_query_changed(definition, diff_summary)` | `definition.query_id`; `diff_summary[i]["id"]` for each node-diff entry |
| `_definition_changed(definition, diff_summary)` | `definition.node_id` (the `CoreArtifactDefinition` id, already present in the gathered model); `diff_summary[i]["id"]` |
| `_transform_changed(definition, repo_diff)` | `definition.dependencies`, `definition.dependencies_complete`; `repo_diff.files_added`, `files_changed`, `files_removed` |

See `contracts/pipeline-predicates.md` for the full signatures and behavior on each input combination.

## 9. Relationships not changed

- `CoreArtifactDefinition` → `CoreGraphQLQuery` (already present).
- `CoreArtifactDefinition` → `CoreTransformation` (already present).
- `CoreArtifactDefinition` → `targets` (`CoreStandardGroup` — already present).
- `CoreTransformation` → `CoreRepository | CoreReadOnlyRepository` (already present).

No new edges. The closure mechanism is entirely about scalar attributes on `CoreTransformation`.

## 10. Migration

Per Decision 11 and SC-005: no operator-run data migration. The two new attributes are added optional/nullable. Existing transforms keep `dependencies = null` until their next natural re-import. The pipeline predicate is null-tolerant.

## 11. Out-of-scope data shapes (deferred)

These are not added in this feature, but the design accommodates them:

- `CoreTransformation.content_hash: Text` — Phase 3 cross-branch fingerprint (Out of Scope per spec).
- `InfrahubWatchConfig.strict: bool` — would let Python opt out of the package-directory floor.
- `InfrahubWatchConfig.exclude: list[str]` — would let users prune the auto-detected closure.
- `CoreArtifactDefinition` per-definition `dependencies` (for definition-level files beyond the transform's closure) — not needed; the definition's signal is the node-id check (`_definition_changed`).
