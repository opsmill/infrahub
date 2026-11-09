# Phase 0 Research: Definition Fingerprint Foundation

The spec is unusually complete: its **Assumptions** section explicitly delegates the
open choices (hash algorithm, watch config representation, group-identity form) as
implementation details. This document records the resolved decisions and the codebase
facts they rest on. No `NEEDS CLARIFICATION` items remain that block planning.

## Decision 1 - Hash algorithm

**Decision**: SHA-256, hex digest, over a canonical UTF-8 byte serialisation of the
composed input tuple.

**Rationale**: The spec's assumptions name SHA-256 hex as the reasonable default and
state the exact algorithm is an implementation detail provided it is deterministic and
stable across processes and Infrahub versions. SHA-256 is collision-resistant and
stdlib (`hashlib`, no new dependency, satisfies Principle VII). Existing checksum code
uses MD5 (`hashlib.md5(..., usedforsecurity=False)` for artifact content), but MD5's
collision weakness is undesirable for a change-detection signal that gates
regeneration; the cost difference is irrelevant at this scale.

**Alternatives considered**: MD5 (matches existing checksum code) - rejected for
collision-resistance; `HashableModel.get_hash()` (MD5 over a Pydantic model) - rejected
because the fingerprint inputs are not naturally one Pydantic model and we want an
explicit, canonical, order-independent serialisation we fully control.

**Implication**: Changing the algorithm later invalidates all stored fingerprints and
forces a full re-import - acceptable over-regeneration per the spec.

## Decision 2 - Where computation lives

**Decision**: A new `backend/infrahub/git/fingerprint/` package with small,
constructor-injected components (per `backend-component-design`):

- `blob_resolver.py` - resolves `{repo_relative_path: blob_sha}` from the git tree at
  the imported commit (GitPython `Repo(worktree).commit(commit).tree`). Reads git
  metadata only, never file contents (FR-009b).
- `composer.py` - layered pure composers, each with a single entry method operating on
  passed-in entities: `compose_query`, `compose_transformation`, `compose_artifact_definition`,
  `compose_generator_definition`. Collaborators (blob resolver, hasher) are injected;
  the definition/config being hashed is a method argument.
- `registry.py` - a per-import in-memory `{definition-key: fingerprint}` snapshot so
  higher levels compose the freshly-computed lower-level value (FR-015a).

**Rationale**: The import already builds config objects and the closure per type in
`git/integrator.py`. Fingerprint is computed there, alongside `dependencies` /
`dependencies_complete`, and passed into the SDK create/update payload. Factoring the
pure hashing logic out of the Prefect flow keeps it unit-testable without a stack
(Principle IV: the no-mock rule is the forcing function).

**Alternatives considered**: Computing inline in `integrator.py` - rejected, it would
bury pure logic inside a Prefect flow and force integration tests for what should be
fast unit tests. A single monolithic composer - rejected in favour of one composer per
layer to mirror the layered composition (FR-015) and keep each testable in isolation.

## Decision 3 - Import ordering and the consistent-snapshot registry (FR-015a)

**Decision**: Within a single import, compute fingerprints in dependency order -
**queries first, then transformations and generator definitions, then artifact
definitions** - populating an in-import registry keyed by definition name/kind. Higher
levels read the registry, never a previously-stored graph value.

**Rationale**: The importer's `_apply_*` methods run per type today. Artifact
definitions reference their transform by name (`transformation: str`) and both artifact
and generator definitions reference their target group by name (`targets: str`); the
transformation references its query by name. A change to a query in an import must
propagate into the dependent transformation and artifact-definition fingerprints in the
*same* import, otherwise a dependent definition lags by one import - a direct violation
of the non-negotiable invariant. A registry populated in dependency order is the minimal
mechanism that guarantees the snapshot is internally consistent.

**Codebase fact**: `git/integrator.py` already resolves the imported `commit` throughout
the flow and builds the closure per type; the change is to sequence the phases and thread
a registry through them, not to rebuild any machinery.

## Decision 4 - Watch three-state discriminator (FR-016/017/019)

**Decision**: Use `config.watch is None` as the discriminator. `watch` absent (`None`)
=> fold the imported commit id into the fingerprint (unstable, safe default). `watch`
present (an `InfrahubWatchConfig`, **even with an empty `files` list**) => omit the
commit id (stable, precise). No change to the SDK config *shape* is required.

**Rationale / codebase fact**: In `python_sdk/infrahub_sdk/schema/repository.py`,
`watch: InfrahubWatchConfig | None = Field(default=None, ...)` on the Jinja2, Python,
and generator configs. The parsed config **already** distinguishes absent (`None`) from
present. The collapse the spec warns about is only in the *closure builder*
(`git/closure_builder/watch.py` line 44: `if watch is None or not watch.files: return`),
which treats both as "no expansion". Fingerprint computation reads the config directly
and branches on `is None`, so it observes the distinction the closure builder discards.

**YAML mapping**: `watch:` with no value parses to `None` (absent -> unstable). An
explicit empty declaration is `watch: {}` or `watch: {files: []}` -> a present config
object -> stable. This matches the epic's `watch: []` / `watch: [files]` shorthand as
described in the spec's assumptions.

**Alternatives considered**: Changing the config to a bare list or adding an explicit
sentinel - rejected as unnecessary; the `| None` union already carries the distinction,
and FR-019 only requires that the two states be *distinguishable* and that fingerprint
computation *branch* on them, both satisfied. (If review prefers a more explicit config
shape, that is in scope per the spec but not required for correctness.)

## Decision 5 - Group identity, not membership (FR-011/012/013)

**Decision**: Fold the **resolved target-group node id** into artifact-definition and
generator-definition fingerprints. Resolve the group by its config name (`targets`) to
its node id during import; membership is never read for the fingerprint.

**Rationale**: FR-011/FR-013 specify "the related group id". Re-pointing `targets` to a
different group must invalidate the fingerprint; adding/removing a member must not.
Hashing the resolved group id captures identity exactly and is invariant to membership
churn, which stays on the existing per-member resolution path. Group names are unique,
so the config name is a valid identity proxy, but the spec asks for the id explicitly
and the id is stable under a rename of an unchanged group.

**Codebase fact**: The artifact-definition config (`InfrahubRepositoryArtifactDefinitionConfig.targets`)
and generator-definition config (`InfrahubGeneratorDefinitionConfig.targets`) carry the
group **name**. `compare_artifact_definition` already reads
`existing_artifact_definition.targets.peer.name.value`, showing the peer group is
resolvable during import; the peer's id is available on the same relationship.

**Alternatives considered**: Hash the group *name* - simpler (no lookup) but does not
match the spec's "id" wording and is not stable under an (unchanged-group) rename;
deferred unless review prefers it. Hash membership - explicitly forbidden by FR-013.

## Decision 6 - Definition's own source file in the closure (FR-009a/FR-012)

**Decision**: Rely on the existing closure already including the definition's own source
file (Python package-directory floor; Jinja2 template seeded and walked transitively;
generator `.py`). The fingerprint folds every closure path's blob SHA, so the own-source
file is covered independent of `watch:`.

**Rationale / codebase fact**: The closure builders
(`git/closure_builder/python_closure.py`, `jinja2_closure.py`) already produce the
package-directory floor and template transitive closure (INFP-409); `dependencies` on
the stored config carries these canonical paths. The fingerprint composes over
`dependencies` by resolving each path's blob SHA - so editing the transform's own
`.py`/template changes a blob SHA and thus the fingerprint even when `watch: {}`
(explicitly empty). No closure change is needed; this is a property to *assert in tests*
(US2 scenario 6, US4 scenario 4), not to build.

## Decision 7 - Fragment inlining and the query fingerprint (FR-008)

**Decision**: Hash the **stored, fragment-inlined** `query` text.

**Rationale / codebase fact**: `render_query()` in
`python_sdk/infrahub_sdk/graphql/query_renderer.py` inlines fragments at import time; the
integrator stores the rendered self-contained text on `CoreGraphQLQuery.query`. Hashing
the stored value (not raw file bytes) makes logically-identical queries that Infrahub
normalises identically hash identically (US1 scenario 4) and needs no separate fragment
resolution.

## Decision 8 - Canonicalisation (FR-014)

**Decision**: Closure -> sorted list of `(path, blob_sha)` pairs (the closure
`dependencies` is already canonicalised/sorted/deduplicated by `ClosureResult`).
`parameters` and any structured input -> canonical JSON (`json.dumps(..., sort_keys=True,
separators=(",", ":"))`). Field order within the composed tuple is fixed and documented
in `contracts/fingerprint-composition.md`.

**Rationale**: Logically-identical inputs must always hash identically regardless of
ordering (edit-then-revert net-zero, SC-004). `ClosureResult` already sorts and dedupes
dependency paths, so only blob-SHA pairing and JSON canonicalisation are added.

## Open items for reviewer confirmation (flagged, non-blocking)

Carried from the spec's Assumptions; none block implementation:

1. **FR-012a**: `class_name` + `convert_query_response` are folded into the *generator*
   fingerprint though the epic's bullet list omits them (completeness condition FR-021).
   Conservative - can only over-regenerate.
2. **FR-009a/FR-012**: the definition's own source file is explicitly in the closure
   (the epic only implied it). Conservative.
3. **Group identity form** (Decision 5): group node id vs group name - defaulting to id
   per spec wording.
