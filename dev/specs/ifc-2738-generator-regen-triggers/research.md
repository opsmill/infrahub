# Phase 0 Research

This document resolves the technical decisions behind the plan. There are no remaining `NEEDS CLARIFICATION` markers: the feature is an explicit replication of the shipped INFP-409 machinery, and the codebase investigation confirmed every reused component is present and shaped as the spec assumes.

## Verified state of the reused INFP-409 machinery

All of the following were confirmed present in the codebase before planning. This feature wires generators into them; it does not rebuild them.

| Component | Location | Reused as |
|---|---|---|
| Predicates `_query_changed`, `_definition_changed`, `_transform_changed` | `backend/infrahub/proposed_change/tasks.py` (~1301-1434) | Generalized via Protocol (FR-005), not duplicated |
| `PredicateOutcome` (matched + reason) | `backend/infrahub/proposed_change/tasks.py` (~1286-1298) | Reused unchanged; carries the why-trail |
| `DefinitionSelect` IntFlag | `backend/infrahub/proposed_change/tasks.py` (~1444-1475) | Reused; generator gate sets the same flags |
| `PythonClosure` (`supports`/`build`) | `backend/infrahub/git/closure_builder/python_closure.py` | `supports()` widened to accept generator config (FR-002) |
| `TransformConfig` union | `backend/infrahub/git/closure_builder/protocols.py` | Widened to include `InfrahubGeneratorDefinitionConfig` (FR-002) |
| Aggregator (`build` → per-language builder → `append_manifest_path` → `union_watch_files`) | `backend/infrahub/git/closure_builder/dispatcher.py` | Reused as-is; manifest + watch steps apply to generators automatically |
| `canonicalize_path` | `backend/infrahub/git/closure_builder/canonicalizer.py` | Reused on both write (closure) and read (diff) sides |
| `union_watch_files` (reads `transform_config.watch`, recursive dirs, warns on no-match) | `backend/infrahub/git/closure_builder/watch.py` | Works for generators once the config has a `watch` field (FR-014) |
| `append_manifest_path` (`.infrahub.yml`) | `backend/infrahub/git/closure_builder/post_processing.py` | Reused; whole-file `.infrahub.yml` conservatism carries over |
| `InfrahubWatchConfig` (strict, `extra="forbid"`) | `python_sdk/infrahub_sdk/schema/repository.py` | Reused as-is; added to generator config (FR-014) |
| Per-repo diff decoupled from `sync_with_git` | INFP-409 US5 machinery | Verified, not rebuilt (FR-008) |

## Decision 1 — Generalize the three predicates behind a structural `Protocol`, do not duplicate them

**Decision**: Introduce a `typing.Protocol` (e.g. `RegenerationDefinition`) declaring the fields the predicates read, and retype `_query_changed`, `_definition_changed`, `_transform_changed` to accept it. Both `ProposedChangeArtifactDefinition` (already satisfies it) and `ProposedChangeGeneratorDefinition` (after FR-004 adds the missing fields) conform structurally with no inheritance change.

**Fields the Protocol must declare** (confirmed by reading the predicate bodies):

- `definition_id: str`, `definition_name: str` — read by `_definition_changed` and in every reason string.
- `query_id: str`, `query_name: str` — read by `_query_changed`. `query_name` is already on the generator model; `query_id` is added by FR-004.
- `dependencies: list[str] | None`, `dependencies_complete: bool | None` — read by `_transform_changed`. Both added by FR-004.

**Rationale**: The predicates read only these named fields; they never touch artifact-specific fields. A structural Protocol is the minimum-surface way to let the shipped functions accept generator definitions without duck-typing (`getattr`) or forcing a shared base class onto two models that otherwise differ. It satisfies Principle VII's two-caller rule the instant it lands.

**Alternatives rejected**:

- *Duplicate the predicates for generators.* Rejected: three near-identical functions drift apart and double the test surface; the spec explicitly calls for generalization (FR-005).
- *Shared Pydantic base class.* Rejected: the two models have different parents (`GeneratorDefinitionModel` vs the artifact model in `message_bus/types.py`) and different field sets; forcing a base couples them more than the predicates require.
- *`getattr`-based duck typing.* Rejected by Principle III (no untyped boundaries).

## Decision 2 — Parametrize the diagnostic wording, do not hardcode "transform"/"artifacts"

**Decision**: The predicate reason strings currently say "transform" and "all artifacts will regenerate". Parametrize the two nouns so generator runs read correctly (e.g. "generator" and "all instances of this generator will run"). Carry the nouns on the Protocol as two literal-valued properties (e.g. `source_noun` → `"transform"` / `"generator source"`, `instance_noun` → `"artifacts"` / `"instances"`), supplied by each concrete model, so the predicate stays a pure function and reads the wording off the definition it was handed.

**Rationale**: Keeps the predicate body single-sourced while making logs accurate for both callers. Reading the noun off the model (rather than passing a flag at every call site) means call sites need no extra argument and a future third caller just declares its own nouns.

**Alternatives rejected**:

- *Leave the artifact wording.* Rejected: US5/FR-010 require the log to read correctly for generators; "all artifacts will regenerate" on a generator run is misleading.
- *Pass a noun argument at each call site.* Rejected: more error-prone (every call site must remember to pass it) than a property on the typed model.

## Decision 3 — Definition-level gate swap mirrors the shipped artifact selection gate (FR-006)

**Decision**: In `run_generators`, replace the `DefinitionSelect.FILE_CHANGES` clause `source_branch_sync_with_git AND branch_diff.has_file_modifications` with `_query_changed OR _definition_changed OR _transform_changed(repo_diff)`, evaluated against the per-definition repo diff via the existing `_repo_diff_or_none` lookup. Keep the `MODIFIED_KINDS` clause exactly as today. Log each predicate's `reason` at INFO, identical to `refresh_artifacts`.

**Rationale**: This is a line-for-line parallel of the already-shipped artifact selection gate in `refresh_artifacts`. The inputs (`diff_summary`, per-repo diff, the gathered definition) are all already available in `run_generators`. `query_id` comes from `generator.query.peer.id` (the gather already reads `generator.query.peer.name.value`, so the peer is loaded).

## Decision 4 — Per-member gate swap mirrors `validate_artifacts_generation` (FR-007, primary risk)

**Decision**: In `request_generator_definition_check`, compute `managed_branch` from the same three predicates (`_query_changed OR _definition_changed OR _transform_changed`) instead of unconditionally from `source_branch_sync_with_git`, then pass that boolean into `_run_generator(instance_id, managed_branch, impacted_instances)` exactly as today.

**Why this preserves the never-under-run invariant** (the risk the spec flags): `_run_generator` returns `True` when `not instance_id or managed_branch`, else `instance_id in impacted_instances`. The three categories of legitimate run remain covered:

1. **Category 1 (data change)** is unaffected: it flows through `impacted_instances` (computed from `get_field_level_impacted_subscribers`), which is independent of `managed_branch`. An instance whose data changed is in `impacted_instances` and runs regardless.
2. **Category 2 (new target-group member)** is unaffected: a new member has `instance_id = None`, so `not instance_id` is `True` and it runs regardless of `managed_branch`.
3. **Category 3 (closure/query/definition change)** is exactly what the new `managed_branch` now captures: when any predicate fires, `managed_branch = True` and every existing instance re-runs, which is the intended "the generator's source changed, re-run all instances" behavior.

The only behavior change is the *narrowing* of category 3: previously `managed_branch` was `True` for any git sync; now it is `True` only when the closure actually intersects the diff. Categories 1 and 2 still force their runs through the other two branches of `_run_generator`, so no instance that should run is skipped. This is the same reasoning INFP-409 applied to `validate_artifacts_generation`, which already computes `managed_branch` from these predicates.

**Fallback safety**: `_transform_changed` returns `matched = repo_diff.has_modifications` whenever `dependencies is None` or `dependencies_complete is not True`, so a legacy or failed-closure generator yields `managed_branch = True` on any file change — the never-under-run fallback.

**Alternatives rejected**:

- *Keep `managed_branch = source_branch_sync_with_git` and filter later.* Rejected: that is exactly the blunt gate this feature removes; it re-runs every instance on any sync.

## Decision 5 — `query_id` plumbing across BOTH construction sites (FR-004)

**Decision**: Add `query_id: str` to `ProposedChangeGeneratorDefinition` and `dependencies` / `dependencies_complete` as `list[str] | None` / `bool | None`. The model is constructed in **two** places, both of which must set the new fields:

- `backend/infrahub/proposed_change/tasks.py` (`run_generators`, ~354) — the proposed-change pipeline path; this is where the predicates are evaluated.
- `backend/infrahub/generators/tasks.py` (`run_generator_definition`, ~156) — the standalone / post-merge run path. It does not evaluate the new predicates, but it constructs the same model, so it must still populate `query_id = generator.query.peer.id` (and read the two attributes) or model validation fails.

**Field optionality**: `dependencies` and `dependencies_complete` default to `None` (matching the null-tolerant pipeline). `query_id` is populated from `generator.query.peer.id` at both sites — the peer is already prefetched (the gather reads `query.peer.name.value` and `query.peer.models.value`), so `.peer.id` is free.

**Rationale**: A generator with an unresolvable query peer must err toward running (spec Edge Cases): the predicate set still falls back via `_transform_changed`, and a missing `query_id` simply means `_query_changed` never matches — it does not suppress the other run signals. Missing the second construction site would raise a `ValidationError` on the post-merge path; tasks must update both.

## Decision 6 — `dependencies_complete` is only ever `False` on closure-build failure for generators

**Decision**: Build each generator's closure with the existing aggregator. On the happy path the closure is complete (`True`); it is `False` only when `union_watch_files`/the builder hit an isolated failure (the aggregator's `except ISOLATED_FAILURES` path returns `complete=False`). When a non-empty `watch.files` is declared, `union_watch_files` already forces `complete=True` (FR-017).

**Rationale**: Generators are Python-only and AST import analysis is rejected (spec Out of Scope), so there is no unresolved-reference detector to set `False` the way the Jinja2 walker does for templates. This is the documented Known Limitation: `dependencies_complete` is still load-bearing because `_transform_changed` reads it unconditionally — a failed-closure generator with `complete=False` runs-always instead of trusting an empty closure. No code change is needed to get this behavior; it falls out of the reused aggregator.

## Decision 7 — Build the closure in `_build_generator_definitions`, thread the result to the apply step (parallels INFP-409 Decision 1)

**Decision**: Build each generator's closure in `_build_generator_definitions` (integrator.py ~979), which is the only generator-import function with worktree access — it already calls `self.get_worktree(identifier=commit or branch_name)` (lines ~988-989, `commit_wt` / `branch_wt`). Use `Path(branch_wt.directory)` as `worktree_root`, mirroring the Python-transform site (integrator.py ~1135). The downstream functions `_apply_generator_definitions`, `_create_generator_definition`, `_update_generator_definition`, and `_generator_requires_update` have **no** worktree in scope, so the `ClosureResult` must be threaded from the build step to them.

**Threading mechanism**: `_build_generator_definitions` currently returns `list[InfrahubGeneratorDefinitionConfig]`. Carry the closure alongside each config so the apply step can persist it without re-opening the worktree. Recommended: build the closure in the same loop that produces the configs and attach `dependencies` / `dependencies_complete` to a small wrapper (or a parallel dict keyed by generator name) that `_apply_generator_definitions` consumes; `_create_/_update_generator_definition` then write the two attributes onto the node payload exactly as `_update_generator_definition` already writes `file_path`, `class_name`, etc.

**`_generator_requires_update`**: must also compare the stored closure against the freshly built one so a content change that alters dependencies (but leaves the other compared fields equal) still triggers a node update — otherwise a generator's `dependencies` could go stale.

**Rationale**: Same lifecycle argument as INFP-409 — the closure is a property of source content and only changes on re-import; pipeline-time evaluation is a cheap set intersection. The artifact import path already calls `build_default_closure_builder(...).build(...)` at the transform import sites (integrator ~385, ~1117) and persists immediately because build and persist are co-located there; the generator path splits them across functions, hence the explicit threading.

**Known Limitation accepted** (from spec): the closure is rebuilt on every re-importing commit (a `git ls-files` walk of the package directory). Acceptable for this delivery; revisit only on a measured regression.

## Decision 8 — SDK `watch:` field added directly to the submodule, reusing `InfrahubWatchConfig` (FR-014..FR-017)

**Decision**: Add `watch: InfrahubWatchConfig | None = None` to `InfrahubGeneratorDefinitionConfig` in `python_sdk/infrahub_sdk/schema/repository.py`. No new type. The strict object form (`extra="forbid"`) and list-form rejection come for free from the reused model. Because the aggregator already calls `union_watch_files`, which reads `transform_config.watch`, the field is functional end-to-end with no backend wiring beyond FR-002's union widening.

**Rationale**: This is the exact pattern INFP-409 used to add `watch:` to the transform configs. The submodule change is committed explicitly (constitution Git Workflow). The remaining SDK work is parsing tests, docs, and the changelog.

**Note on `union_watch_files` requiring the attribute**: `union_watch_files` accesses `transform_config.watch`; without the field this would raise `AttributeError` for generators. So FR-014 is a prerequisite for routing generators through the aggregator, not merely a user-facing nicety. This is captured in the task ordering.

## Decision 9 — Artifact regression coverage is mandatory because the predicates are shared (FR-013)

**Decision**: The predicate generalization (FR-005) edits functions artifacts also call. Add explicit assertions (or keep the existing artifact predicate/selection tests green and extend them) proving artifact selection and artifact log wording are byte-for-byte unchanged after the Protocol retype and the noun parametrization.

**Rationale**: A shared refactor that silently changed artifact wording or selection would be a regression on a shipped feature. The existing `test_artifact_regen_selection.py`, `test_predicates.py`, and `test_predicate_logging.py` are the regression surface; they must stay green and the artifact reason strings must be asserted verbatim.

## Out of scope (confirmed, inherited from spec)

- Computed attributes (IFC-1797) — tracked separately.
- Cross-branch fingerprint compare — deferred from INFP-409; edit-then-revert across branches still over-runs.
- AST-based Python import analysis — rejected; cross-package dependencies are declared via `watch.files`.
