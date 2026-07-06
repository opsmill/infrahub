# Phase 1 Data Model: Definition Fingerprint Foundation

## Schema attribute (added to four node kinds)

One attribute, identical shape, added to each target node's hand-authored core schema
definition. Declared with `Attr(...)` in `backend/infrahub/core/schema/definitions/core/`.

| Property     | Value                          | Source req.        |
|--------------|--------------------------------|--------------------|
| `name`       | `fingerprint`                  | FR-001             |
| `kind`       | `Text`                         | FR-002             |
| `optional`   | `True` (null permitted)        | FR-002             |
| `branch`     | `BranchSupportType.AWARE`      | FR-003             |
| `read_only`  | `False` (writable via mutation)| FR-004             |
| `unique`     | `False`                        | -                  |

**Null semantics**: null = "pre-feature node, never re-imported"; consumers treat null
as "unknown -> regenerate". This foundation does not backfill (no migration).

### Placement

| Node kind                 | File                                                              | Notes                                                       |
|---------------------------|-------------------------------------------------------------------|-------------------------------------------------------------|
| `CoreGraphQLQuery`        | `.../core/graphql_query.py`                                        | Alongside `query` (TextArea).                               |
| `CoreTransformation`      | `.../core/transform.py` (the `GenericSchema`)                     | Declared once on the generic; inherited by Python + Jinja2. |
| `CoreArtifactDefinition`  | `.../core/artifact.py`                                             |                                                             |
| `CoreGeneratorDefinition` | `.../core/generator.py`                                           |                                                             |

`CoreTransformation` is a `GenericSchema`; `CoreTransformPython` and `CoreTransformJinja2`
inherit via `inherit_from=[InfrahubKind.TRANSFORM]`, so the single attribute on the
generic propagates to both concrete kinds through `NodeInheritanceHandler`.

## Fingerprint composition entities (in-import, not persisted)

These are internal frozen dataclasses used during computation. Only the resulting hex
digest is persisted (on the `fingerprint` attribute).

### `ClosureFingerprintInput`

Sorted tuple of `(repo_relative_path, git_blob_sha)` pairs, derived from the stored
`dependencies` (canonical paths, already sorted/deduped by `ClosureResult`) by resolving
each path's blob SHA at the imported commit (FR-009b). File contents are never read.

### In-import fingerprint registry

`{ (kind, name): fingerprint_hexdigest }` populated in dependency order within one
import (FR-015a). Read by higher layers; never reads a previously-stored graph value.

## Composition inputs per kind (what is hashed)

Authoritative field-level contract: `contracts/fingerprint-composition.md`. Summary:

| Kind                      | Hashed inputs                                                                                                                              | Excluded                                                        |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| `CoreGraphQLQuery`        | stored fragment-inlined `query` text (FR-008)                                                                                              | -                                                              |
| `CoreTransformation` (Py) | connected query fingerprint; sorted `(path, blob_sha)` closure (incl. own `.py`); `class_name`; `convert_query_response`; commit-id iff `watch is None` | `timeout`, `description` (FR-010, FR-015b)                     |
| `CoreTransformation` (J2) | connected query fingerprint; sorted `(path, blob_sha)` closure (incl. template); `template_path`; commit-id iff `watch is None`            | `timeout`, `description`                                       |
| `CoreArtifactDefinition`  | transformation fingerprint; canonical `parameters`; `content_type`; `artifact_name`; target-group id                                       | group *membership* (FR-013)                                    |
| `CoreGeneratorDefinition` | connected query fingerprint; sorted `(path, blob_sha)` closure (incl. own `.py`); canonical `parameters`; `class_name`; `convert_query_response`; target-group id; commit-id iff `watch is None` | `execute_in_proposed_change`, `execute_after_merge`, group membership (FR-012a) |

## Layering (FR-015)

```text
CoreGraphQLQuery.fingerprint
        │
        ├────────────► CoreTransformation.fingerprint ───► CoreArtifactDefinition.fingerprint
        │
        └────────────► CoreGeneratorDefinition.fingerprint
```

Each level reuses the level below, from the same-import registry (consistent snapshot,
FR-015a).

## Watch state -> fingerprint stability

| `.infrahub.yml` `watch`      | Parsed config        | Commit id folded? | Fingerprint stability            |
|------------------------------|----------------------|-------------------|----------------------------------|
| absent                       | `None`               | Yes               | Changes every commit (safe default) |
| `watch: {}` / `{files: []}`  | present, empty files | No                | Stable across unrelated commits  |
| `watch: {files: [...]}`      | present, files       | No                | Declared files join closure; stable otherwise |

## Generated / regenerated artifacts (FR-023)

Additive schema change => regenerate and commit:

- `backend/infrahub/core/schema/generated/*` and `backend/infrahub/core/protocols.py` - `uv run invoke backend.generate`
- `schema/schema.graphql` - `uv run invoke schema.generate-graphqlschema`
- `schema/openapi.json` - `uv run invoke schema.generate-jsonschema`
- `frontend/app/src/shared/api/graphql/generated/*` - `cd frontend/app && pnpm codegen`

CI `docs.validate` and generated-file validation must pass (SC-009).
