# Contract: Fingerprint Composition

This is the internal contract for how each definition's `fingerprint` is composed. It is
the authoritative field-level enumeration referenced by `data-model.md`. Consumers rely
only on the *observable* property: **any change to a hashed input changes the digest;
any change to an excluded input does not.** The exact serialisation is an implementation
detail (SHA-256 hex over a canonical UTF-8 tuple serialisation), but the *set* of hashed
inputs and their canonicalisation are contractual (FR-021 completeness condition).

## Canonicalisation rules (FR-014)

- **Closure**: sorted list of `(repo_relative_path, git_blob_sha)` pairs. Paths come from
  the stored `dependencies` (already canonical/sorted/deduped); blob SHAs resolved at the
  imported commit from the git tree (metadata read, not file contents).
- **Structured values** (`parameters`): canonical JSON - `sort_keys=True`, no whitespace.
- **Scalars** (`class_name`, `template_path`, `content_type`, `artifact_name`,
  `convert_query_response`): stringified in a fixed, documented field order.
- **Commit id**: folded **iff** `config.watch is None` (absent). Present-but-empty `watch`
  omits it.

## CoreGraphQLQuery (FR-008)

```text
fingerprint = H( query_text )
```

- `query_text` = the **stored, fragment-inlined** `query` attribute.
- Nothing else. No commit id, no closure (a query has no watch/closure).

## CoreTransformation - Python (FR-009, FR-009a/b, FR-010, FR-015b)

```text
fingerprint = H(
    query_fingerprint,                       # from same-import registry
    sorted[(path, blob_sha)],                # closure incl. own .py (package-dir floor)
    class_name,
    convert_query_response,
    commit_id   if config.watch is None else <omitted>,
)
```

Excluded: `timeout` (execution limit, not output - FR-010), `description` (FR-015b).

## CoreTransformation - Jinja2 (FR-009, FR-009a/b)

```text
fingerprint = H(
    query_fingerprint,
    sorted[(path, blob_sha)],                # closure incl. template (seeded + walked)
    template_path,
    commit_id   if config.watch is None else <omitted>,
)
```

Excluded: `timeout`, `description`.

## CoreArtifactDefinition (FR-011, FR-013)

```text
fingerprint = H(
    transformation_fingerprint,              # from same-import registry
    canonical_json(parameters),
    content_type,
    artifact_name,                           # the name template
    target_group_id,                         # identity, resolved from `targets`
)
```

Group **identity** included (re-point => change); group **membership** excluded
(add/remove member => no change). No closure/commit id of its own - it inherits the
transformation's (which already carries the watch-driven commit id when applicable).

## CoreGeneratorDefinition (FR-012, FR-012a, FR-013)

```text
fingerprint = H(
    query_fingerprint,
    sorted[(path, blob_sha)],                # closure incl. own .py
    canonical_json(parameters),
    class_name,                              # FR-012a (epic omits; completeness requires)
    convert_query_response,                  # FR-012a
    target_group_id,                         # identity
    commit_id   if config.watch is None else <omitted>,
)
```

Excluded: `execute_in_proposed_change`, `execute_after_merge` (when/whether it runs, not
output - FR-012a); group membership (FR-013).

## Completeness invariant (FR-021)

Every output-affecting field originating in the manifest MUST appear above. Adding a new
output-affecting manifest field to any definition kind REQUIRES adding it here and to the
composer, or editing only that field would leave the fingerprint stable and cause
under-regeneration. This is what makes the later `.infrahub.yml` closure drop (IFC-2775)
safe.

## Scope guard (FR-020)

This contract defines only how the value is *produced*. No consumer reads it in this
feature: no trigger rewired, no regeneration/recompute gate changed. Existing
regeneration behaviour is observably unchanged (SC-008).
