# Phase 0 Research

Resolves the open technical questions raised by `spec.md`.

## R-1: Schema `order_by` field shape

**Decision**: Keep the wire shape as `list[str] | None`. Extend semantics only — no Pydantic field-type change.

**Rationale**: `order_by` is declared as `list[str] | None` on `GeneratedBaseNodeSchema` (`backend/infrahub/core/schema/generated/base_node_schema.py:86-90`) and is propagated through OpenAPI, GraphQL, and the SDK as a string array. Changing the wire shape would force every consumer (frontend, SDK, generated OpenAPI clients) to handle a new variant. The new syntax fits inside the existing string entries.

**Alternatives**:

- Move to a structured object per entry (`{field, direction}`): rejected — breaks every existing consumer and the spec explicitly preserves the wire shape.
- Add a sibling `order_by_v2` field: rejected — duplicates state and complicates inheritance.

## R-2: Where to centralize parsing

**Decision**: Introduce a single `parse_order_by_entry(entry: str) -> ParsedOrderByEntry` helper plus a `ParsedOrderByEntry` frozen dataclass in `backend/infrahub/core/schema/order_by.py` (new module). All four call sites consume it:

1. `SchemaBranch.validate_order_by()` — load-time validation.
2. `NodeGetListQuery` — top-level list path.
3. `RelationshipGetListQuery` — relationship-peer path.
4. `NodeGetHierarchyQuery` — hierarchy path.

**Rationale**: Today each call site does `entry.split("__", maxsplit=1)` independently and assumes `<field>__<attr_prop>`. Adding `node_metadata__<field>__<direction>` and the optional `__asc`/`__desc` suffix to three independent split-sites guarantees drift. A central parser + dataclass also gives us a single place to fail-fast at schema load (FR-004, FR-006, FR-007) and a typed payload that the three query call sites consume without re-parsing.

**Alternatives**:

- Inline parsing at each call site: rejected — Principle VII says three similar lines are fine, but here we have three call sites *plus* a validator, plus the path is non-trivial (4 distinct grammar shapes — see contracts/grammar.md).
- Extend the existing `parse_schema_path` to return direction: rejected — that helper returns a `SchemaAttributePath` chain unrelated to the new metadata-prefix case; conflating them blurs responsibilities.

## R-3: Direction propagation through the three query paths

**Decision**:

- Top-level (`NodeGetListQuery`): `_get_schema_order_field_requirements` already builds `FieldAttributeRequirement(order_direction=...)` (`backend/infrahub/core/query/node.py:2239-2263`). Today it hardcodes `OrderDirection.ASC` at line 2249 and 2260; thread parsed direction in instead. Existing `FieldAttributeRequirement.order_direction` flows into the rendered `ORDER BY` clause.
- Relationship-peer (`RelationshipGetListQuery`) and hierarchy (`NodeGetHierarchyQuery`): currently append `subquery_result_name` raw (no direction) at `relationship.py:971` and `node.py:2558`. Append `f"{subquery_result_name} {direction.value}"` instead, where `direction` is the parsed direction (`OrderDirection.ASC` or `OrderDirection.DESC`). Cypher accepts an explicit direction token after each column in `ORDER BY`.

**Rationale**: Direction is already a first-class concept on the top-level path (it's just hardcoded today). The relationship-peer and hierarchy paths emit raw column names into a comma-separated `ORDER BY` clause assembled elsewhere; suffixing each with the direction keyword is the minimal change.

**Alternatives**: Push direction into `build_subquery_order` and have it materialize a pre-ordered result — rejected; the subquery materializes a single value per node, not a sort, and `ORDER BY` in the outer query is the correct seam.

## R-4: Node-metadata ordering at the three paths

**Decision**:

- Top-level: reuse the existing `_get_metadata_order_fields()` extraction pattern (`node.py:1699-1709`) by feeding it the parsed metadata entries from schema `order_by` (today it only reads `requested_order.node_metadata`).
- Relationship-peer + hierarchy: emit a metadata subquery that resolves `created_at` / `updated_at` for the peer/child node, following the same pattern `_add_created_metadata_subquery` / `_add_updated_metadata_subquery` uses for top-level metadata (`node.py:1742+`). The result of the subquery is then appended to the outer `ORDER BY` with direction.

**Rationale**: FR-008 mandates parity across the three paths. The top-level path already proves the cypher pattern; the relationship-peer and hierarchy paths need the equivalent helpers. Restricting metadata to top-level only would be a confusing carve-out and would make the customer's primary use case (peer list of `DocumentationNote` instances ordered by their `created_at`) unsupported.

**Alternatives**: Skip metadata support on relationship-peer/hierarchy — rejected; defeats the customer's blocking pain (spec User Story 1).

## R-5: UUID tiebreaker (FR-013)

**Decision**: Whenever any schema `order_by` entries are in effect, append `<alias>.uuid ASC` after all entries on all three paths. Aliases: `n.uuid` (top-level), `peer.uuid` (relationship-peer and hierarchy).

**Rationale**: Today only the top-level path appends `n.uuid` (`node.py:1953`); the other two paths fall back to `peer.uuid` *only* when no `order_by` is declared (lines 979, 2565). Spec confirms this is the bug the customer hits: millisecond-equal `created_at` shuffles the list. Standardize.

**Alternatives**: Use `last_updated` or `db_id` — rejected; UUID is the only stable, branch-independent, monotonically present identifier.

## R-6: Schema-vs-query precedence (FR-009)

**Decision**: When `requested_order` carries any field (metadata or `disable=False`-with-content), the schema's `order_by` is ignored entirely on the top-level path. Update the condition at `node.py:1908-1917` so `_get_field_requirements` does not also fold in `self.schema.order_by` when `requested_order` is non-empty (today the condition is `bool(self.schema.order_by) or self._get_metadata_order_fields()`, which OR-stacks them).

**Rationale**: Spec edge case is explicit: today they stack as tiebreakers, but the new contract is replace. This eliminates the surprising case where a caller asks for `node_metadata.created_at DESC` and silently inherits a schema-level secondary ASC sort.

**Caveat**: This is a behavior change. It is called out in the spec's "Edge Cases" section as needing changelog coverage.

**Alternatives**: Keep stacking — rejected by spec clarification.

## R-7: Reserved-name enforcement for `node_metadata`

**Decision**: Add `"node_metadata"` to `RESERVED_ATTR_REL_NAMES` in `backend/infrahub/core/constants/__init__.py:28-48`. Existing rejection logic at `schema_branch.py:1166-1174` then enforces it on every attribute and relationship across NodeSchema, GenericSchema, ProfileSchema, and TemplateSchema.

**Rationale**: Mechanism already exists and produces a clear error message. Spec assumes collision risk is empirically negligible and accepts a hard-fail at load (FR-005).

**Alternatives**: Soft-warn-and-rename — rejected; silent rename would corrupt downstream references.

## R-8: Generic inheritance of new syntax

**Decision**: No new inheritance logic. The new entries are strings; the existing inheritance handler (`node_inheritance_handler.py:21-28`) already copies `order_by` whole when the concrete kind hasn't defined its own. The rename-tracking helper (`_update_order_by_for_renamed_attributes`, lines 104-141) needs one guard: skip entries that start with `node_metadata__`, because those reference a reserved metadata field, not a renamable schema attribute.

**Rationale**: Spec clarification locks in existing inheritance semantics. The rename helper is the only spot that interprets entry content and must learn to leave metadata entries alone.

**Alternatives**: None — the spec is explicit.

## R-9: Duplicate / conflicting entry detection (FR-006)

**Decision**: After parsing each entry into `ParsedOrderByEntry(target, direction)`, build a dict keyed by `target` (a normalized tuple such as `("attribute", "name", "value")` or `("metadata", "created_at")`). Reject if the same target appears twice — regardless of whether the directions match. The spec calls out both duplicates and conflicting directions; collapsing them into a single rule ("a target may appear at most once") is simpler and covers both cases.

**Rationale**: Two entries on the same target add no information; the second is always inert. Forcing uniqueness avoids author confusion when one entry has a direction and the other doesn't.

**Alternatives**: Allow duplicates if directions agree — rejected; semantically pointless and makes the error message harder.

## R-10: OpenAPI / JSON-schema documentation

**Decision**: Do not encode the order_by grammar as a JSON-schema `pattern`. Document it in prose in the field description on `GeneratedBaseNodeSchema.order_by`.

**Rationale**: The auto-generated `schema/openapi.json` regenerates from the Pydantic field. Encoding a regex would (a) drift from the validator (which is the source of truth), and (b) reject valid entries for kinds the regex didn't anticipate. Schema authors load schemas through the Infrahub API; the validator's error message (FR-011) is the actionable signal.

**Alternatives**: Add a regex pattern — rejected for the reasons above.

## R-11: Migration / backward compatibility

**Decision**: No data migration needed. Existing `order_by` entries lack a direction suffix and continue to parse as ascending (FR-003). The only breaking case is schemas that literally name an attribute or relationship `node_metadata` — caught at schema load with a clear error.

**Rationale**: Spec is explicit about the back-compat envelope. No deployed data is rewritten.

**Alternatives**: Auto-rewrite — rejected; touching deployed schemas without author consent is worse than failing loudly.
