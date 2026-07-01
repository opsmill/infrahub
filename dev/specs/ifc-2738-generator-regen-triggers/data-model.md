# Phase 1 Data Model

Every entity this feature touches: the two schema attributes added to `CoreGeneratorDefinition`, the pipeline model extended to carry them, the structural Protocol the predicates depend on, and the SDK config field. The canonical-path form and `ClosureResult` shape are reused unchanged from INFP-409 and are referenced, not redefined.

## 1. `CoreGeneratorDefinition` — schema additions (FR-001)

Two new attributes on `CoreGeneratorDefinition` (`backend/infrahub/core/schema/definitions/core/generator.py`). `CoreGeneratorDefinition` does **not** inherit `CoreTransformation`, so the attributes are added directly to it (this is why the work could not simply reuse the transform attributes). They mirror the INFP-409 attributes on `CoreTransformation` exactly.

| Attribute | Kind | Optional | Default | Purpose |
|---|---|---|---|---|
| `dependencies` | `List` | yes | `null` (sentinel) | Canonical repo-relative paths whose change should trigger this generator: source file + package-directory floor, declared `watch.files`, the `.infrahub.yml` manifest, and the `.gql` query is matched separately via `query_id`. Populated at git-import time. `null` means "no information yet" — the pipeline falls back to the legacy gate for this generator. `[]` is legitimate (genuinely nothing else in the repo). |
| `dependencies_complete` | `Boolean` | yes | `null` | `true` when the closure can be trusted at pipeline time. `false` only on a closure-build failure at import time (see Decision 6 — generators are Python-only, no unresolved-reference detector). `null` only in the pre-feature state; the pipeline treats `null` and `false` identically (both fall back), keeping them distinct for the log. |

### Validation rules

- `dependencies` entries are canonical-path strings (idempotent fixed point of `canonicalize_path`), enforced at write time, identical to the transform attribute.
- `dependencies_complete` carries no cross-field validation; completeness is upheld by the closure builder, not the schema layer.

### State transitions

- **Pre-feature → deployed, generator not yet re-imported:** `dependencies = null`, `dependencies_complete = null`. Pipeline falls back to today's regenerate-on-any-file-change for this generator (FR-009).
- **First re-import under this code:** the aggregator populates `dependencies` (possibly `[]`) and sets `dependencies_complete = True` on the happy path. The generator now participates in precise triggering.
- **Closure-build failure on re-import:** `dependencies = ()` (empty) and `dependencies_complete = False` — the never-under-run fallback (run on any file change).
- **User adds non-empty `watch.files`:** `union_watch_files` unions the declared files and forces `dependencies_complete = True` (trusting the user's declaration, FR-017).

### Branch semantics

Both attributes are `BranchSupportType.AWARE` (the node's existing branch support). Different branches can hold different closures for the same generator, which is correct — a generator's source can differ between branches.

### Generated-file regeneration (FR-001)

Adding the attributes requires regenerating and committing: `backend/infrahub/core/protocols.py` (`CoreGeneratorDefinition` gains the two typed attributes), `backend/infrahub/core/schema/generated/`, `schema/schema.graphql`, `schema/openapi.json`, and `frontend/app/src/shared/api/graphql/generated/`. Run `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`, and `cd frontend/app && pnpm codegen`.

## 2. `ProposedChangeGeneratorDefinition` — model extensions (FR-004)

In-memory Pydantic model (`backend/infrahub/generators/models.py`), subclass of `GeneratorDefinitionModel`. Three fields are added so the predicates can evaluate it.

| Field | Type | Source |
|---|---|---|
| `query_id` | `str` | `generator.query.peer.id` (the peer is already prefetched for `query_name`) |
| `dependencies` | `list[str] \| None` | `generator.dependencies.value` (the new node attribute) |
| `dependencies_complete` | `bool \| None` | `generator.dependencies_complete.value` |

Existing fields already present and reused by the predicates: `definition_id`, `definition_name`, `query_name`.

**Two construction sites** — both must populate the new fields or model validation fails:

| Site | Purpose | Action |
|---|---|---|
| `backend/infrahub/proposed_change/tasks.py` (`run_generators`, ~354) | Proposed-change pipeline; evaluates the predicates | populate `query_id` + read the two attributes |
| `backend/infrahub/generators/tasks.py` (`run_generator_definition`, ~156) | Standalone / post-merge run; does not evaluate predicates | still must set `query_id = generator.query.peer.id` |

`dependencies` / `dependencies_complete` default to `None`, so the post-merge site is unaffected by them; only `query_id` (if made required) forces that site to be updated.

### Validation rules

- `dependencies` is read verbatim from the graph (paths were canonicalized at write time; `canonicalize_path` is idempotent, and the predicate canonicalizes again defensively on the diff side).
- `dependencies_complete` is tri-state from the pipeline's view (`True` / `False` / `None`); the predicate treats `None` and `False` identically but keeps them distinct for diagnostics.

## 3. `RegenerationDefinition` — the structural Protocol (FR-005)

New `typing.Protocol` (location: alongside the predicates in `backend/infrahub/proposed_change/tasks.py`, or a small shared module imported by it). Declares exactly the fields and nouns the three predicates read. Both `ProposedChangeArtifactDefinition` and `ProposedChangeGeneratorDefinition` satisfy it structurally — no inheritance change to either model.

```python
class RegenerationDefinition(Protocol):
    definition_id: str
    definition_name: str
    query_id: str
    query_name: str
    dependencies: list[str] | None
    dependencies_complete: bool | None
    # parametrized diagnostic wording (Decision 2):
    @property
    def source_noun(self) -> str: ...     # "transform" | "generator source"
    @property
    def instance_noun(self) -> str: ...   # "artifacts" | "instances"
```

The three predicates are retyped from `ProposedChangeArtifactDefinition` to `RegenerationDefinition`. Reason strings interpolate `source_noun` / `instance_noun` so they read correctly for both callers. See `contracts/definition-protocol.md` for the full field-by-predicate matrix and the exact reason-string templates.

### Invariants

- The Protocol declares **only** fields the predicates read. Adding a field the predicates do not use is forbidden (keeps the contract honest).
- Artifact reason strings must remain byte-for-byte identical after parametrization when `source_noun = "transform"` / `instance_noun = "artifacts"` (FR-013 regression guard).

## 4. Canonical path form — reused unchanged

Defined in `backend/infrahub/git/closure_builder/canonicalizer.py` (`canonicalize_path`). POSIX separators, leading `/` and `./` stripped, trailing `/` stripped, symlinks not resolved, case preserved, idempotent. Applied symmetrically: the closure builder canonicalizes every path entering `dependencies`; the predicate canonicalizes every path from the repo diff before the set intersection. No change for this feature.

## 5. `ClosureResult` — reused unchanged

Frozen dataclass in `backend/infrahub/git/closure_builder/` (`dependencies: tuple[str, ...]`, `complete: bool`, `unresolved: tuple[...]`). The generator path consumes it identically to the artifact path: persist `result.dependencies` → `dependencies`, `result.complete` → `dependencies_complete`.

## 6. SDK `watch:` on `InfrahubGeneratorDefinitionConfig` (FR-014..FR-017)

`python_sdk/infrahub_sdk/schema/repository.py`. Add one field to the existing `InfrahubGeneratorDefinitionConfig`, reusing the existing `InfrahubWatchConfig` (no new type):

```python
class InfrahubGeneratorDefinitionConfig(InfrahubRepositoryConfigElement):
    model_config = ConfigDict(extra="forbid")
    # ... existing fields ...
    watch: InfrahubWatchConfig | None = Field(
        default=None,
        description="Extra files and directories this generator depends on, in addition to the ones Infrahub detects automatically.",
    )
```

`InfrahubWatchConfig` (reused): `model_config = ConfigDict(extra="forbid")`, `files: list[str] = Field(default_factory=list, ...)`.

### Validation rules

- Object form only: `watch: { files: [...] }`. The list form `watch: [a, b]` is rejected by Pydantic typing; unknown keys (`watch: { fles: [...] }`) are rejected by `extra="forbid"` (FR-015).
- `files` entries are raw user strings; the SDK does not canonicalize them — the backend integrator is the canonicalization authority. Directory entries match recursively (expanded by `union_watch_files` via `git ls-files`).
- A `watch.files` entry matching no tracked file is logged as a warning at import time and does not extend the closure, but does not abort the import and (per FR-017) still forces `dependencies_complete = True` because a declaration was made (FR-016).

## 7. `.infrahub.yml` manifest entry — reused behavior

The aggregator's `append_manifest_path` appends `.infrahub.yml` to every closure it builds. Once generators route through the aggregator, any edit to `.infrahub.yml` re-runs every generator in that repo (whole-file conservatism, accepted Known Limitation). No new entity.

## 8. Pipeline-time predicate inputs (generator caller)

| Predicate | Inputs (generator) |
|---|---|
| `_query_changed(definition, diff_summary)` | `definition.query_id` (FR-004); `diff_summary[i]["id"]` |
| `_definition_changed(definition, diff_summary)` | `definition.definition_id`; `diff_summary[i]["id"]` and per-field detail |
| `_transform_changed(definition, repo_diff)` | `definition.dependencies`, `definition.dependencies_complete` (FR-004); `repo_diff.files_added / files_changed / files_removed` |

## 9. Relationships not changed

`CoreGeneratorDefinition` → `CoreGraphQLQuery` (`query`), → repository, → `targets` (`CoreGroup`) are all unchanged. No new edges. The closure mechanism is entirely scalar attributes on `CoreGeneratorDefinition`.

## 10. Migration

No operator-run migration (parallels INFP-409, SC-005). Both attributes are added optional/nullable; existing generators keep `dependencies = null` until their next natural re-import. The pipeline predicate is null-tolerant (FR-009).

## 11. Out-of-scope data shapes (deferred)

- `CoreGeneratorDefinition.content_hash` — cross-branch fingerprint (out of scope, deferred from INFP-409).
- `InfrahubWatchConfig.strict` / `exclude` — not added here (the model is shaped to accept them later without migration).
