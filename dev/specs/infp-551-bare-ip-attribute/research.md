# Phase 0 Research: Bare IP addresses on IPHost attributes

**Feature**: `specs/infp-551-bare-ip-attribute` | **Date**: 2026-07-28

All facts below were verified against the working tree at `62bd11b59` by direct file reads. Line
numbers are current as of that commit. The idea brief (`bare-ip-attribute.md`) supplied the initial
claims; this document records which held, which changed, and what the plan depends on.

## R1 — The parameter's placement: per-kind parameters classes

**Decision**: add `IPHostAttributeParameters(AttributeParameters)` holding
`allow_prefix: bool = True`, and `IPHostAttributeSchema(AttributeSchema)` carrying the typed
`parameters` field. Register both in the existing kind→class registries.

**Rationale** — verified, the pattern exists and is registered by kind:

- `backend/infrahub/core/schema/attribute_parameters.py:14-22` — `get_attribute_parameters_class_for_kind`
  maps kind → parameters class. Precedents: `NumberPoolParameters`, `TextAttributeParameters`
  (registered for both `Text` and `TextArea`), `ListAttributeParameters`, `NumberAttributeParameters`.
- `backend/infrahub/core/schema/attribute_schema.py:308-314` — `attribute_schema_class_by_kind` maps
  kind → `AttributeSchema` subclass. Precedents: `NumberPoolSchema`, `TextAttributeSchema`,
  `ListAttributeSchema`, `NumberAttributeSchema`.
- `attribute_parameters.py:26` — `AttributeParameters.model_config = ConfigDict(extra="forbid")`.

**Consequence for FR-002 (reject on other kinds)**: two layers, both already built.
`extra="forbid"` makes `allow_prefix` on a `Text` attribute a Pydantic error with no bespoke code.
The explicit reverse guard — an `IPHostAttributeParameters` instance on a non-`IPHost` kind — mirrors
`attribute_schema.py:157-166`, which already raises
`"{Class} can't be used as parameters for {kind}"` for the three existing kinds. One added `isinstance`
branch.

**Alternatives considered**: a top-level `AttributeSchema.allow_prefix` field. Rejected — it would be
*reachable* (if meaningless) on every kind, requiring hand-written per-kind validation, and it would
widen the generic attribute contract rather than a kind-specific one. The PRD fixes this placement as
a constraint, and research confirms it is also the cheaper option.

## R2 — Both validation hooks already receive the schema

**Decision**: make `IPHost.validate_format` and `IPHost._normalize_value` parameter-aware. No
signature changes anywhere.

**Rationale** — this is the single most load-bearing finding, and it holds:

- `backend/infrahub/core/attribute.py:1131` —
  `validate_format(cls, value: Any, name: str, schema: AttributeSchema) -> None` is a classmethod that
  **already receives `schema`**. It can read `schema.parameters.allow_prefix` and raise
  `ValidationError({name: ...})` — the existing error type, already keyed by attribute name, which is
  what FR-003's "error naming the attribute" requires.
- `attribute.py:1150` — `_normalize_value(self, value: Any) -> str` is an **instance** method, and
  `self.schema` is assigned in `__init__` at `attribute.py:120`, before the
  `validate()` / `_normalize_value()` pair runs at `attribute.py:166-167`. So it can read
  `self.schema.parameters.allow_prefix`.

**Consequence**: normalisation decides the stored value, so every downstream surface follows with no
additional code. Confirmed for each:

| Surface | Mechanism | Verified at |
|---------|-----------|-------------|
| Stored value | `IPHost` does **not** override `serialize_value`, so the base returns `self.value` — the normalised string is what is written | `attribute.py:366` is `BaseAttribute.serialize_value`; no IPHost override between 1036-1167 |
| GraphQL | `IPHostType.value = Field(String)` resolves the attribute's `value` | `backend/infrahub/graphql/types/attribute.py:115-116` |
| Uniqueness | `attribute_property_map = {"value": RELATIONSHIP_TO_VALUE_LABEL}` — uniqueness can only compare `value` | `backend/infrahub/core/validators/uniqueness/query/validation.py:22` |
| HFID / display label | Both are derived from the stored attribute value | see R6 |

## R3 — `prefixlen` stays populated, and this is not a fiction

**Decision**: change nothing in `to_db()`. The derived prefix length continues to be written.

**Rationale**:

- `attribute.py:1052-1062` — `IPHost.obj` is `ipaddress.ip_interface(str(self.value))`. For a bare
  `10.0.0.1` this yields `IPv4Interface('10.0.0.1/32')`. So `prefixlen` → `32`, `version` → `4`, and
  `ip_binary` are all still correct and **derived from the bare value**. Nothing needs to remember the
  input form.
- `attribute.py:1158-1166` — `to_db()` writes `version`, `binary_address`, and `prefixlen` whenever
  `value is not None`. Unchanged for flagged attributes.
- `backend/infrahub/core/query/attribute.py:429` — `prefixlen` is an exposed filter name alongside
  `value`, `binary_address`, and `isnull`, comparing `av.prefixlen`. Clearing it would make
  `NULL <= x` evaluate to NULL in Cypher and silently drop flagged rows from containment results —
  the exact silent-exclusion failure mode this design exists to avoid.

**Alternatives considered**: writing `prefixlen = NULL` for flagged attributes so storage matches the
declared semantics. Rejected on the evidence above: it buys nothing user-visible (the contract is
`value`, already bare) and costs silent query exclusion.

## R4 — Immutability is free

**Decision**: declare `allow_prefix` with
`json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value}`.

**Rationale** — verified at `backend/infrahub/core/models.py:279-300`: when a changed property's diff
is itself a `HashableModelDiff` (which `parameters` is), the walker descends into each changed
sub-field, reads that sub-field's **own** `json_schema_extra["update"]`, and emits a `SchemaPath` with
`property_name = f"{prop_name}.{param_field_name}"` — i.e. `parameters.allow_prefix`. It falls back to
the parent field's classification only when the sub-field has none.

`NumberPoolParameters.number_pool_id` (`attribute_parameters.py:196-200`) is the live
`NOT_SUPPORTED` precedent shipped through exactly this path. FR-009 therefore needs **no new code** —
only the correct annotation, plus a test proving it.

`UpdateSupport.NOT_SUPPORTED` and `Visibility.WRITE` both confirmed present at
`backend/infrahub/core/constants/schema.py:16-33`.

## R5 — The internal schema registration point

**Decision**: add `IPHostAttributeParameters` to the `internal_kind` list of the `parameters`
`SchemaAttribute` in `backend/infrahub/core/schema/definitions/internal.py:803-817`.

**Rationale**: `internal.py:122-123` — when `internal_kind` is a list, `object_kind` renders
`" | ".join(cls.__name__ ...)`, which becomes the type annotation on the generated
`GeneratedAttributeSchema.parameters` field. This is the one edit that produces the core-schema diff
and the regenerated artefacts the governance gate refers to. The field already carries
`extra={"update": UpdateSupport.VALIDATE_CONSTRAINT, "visibility": Visibility.WRITE}` — the new
parameters class inherits that treatment, so **FR-013 requires no contract work**: `parameters` is
already published at `WRITE` visibility.

## R6 — Frontend: there is no prefix control to remove

**This is the largest correction to the PRD's assumptions and it reduces the frontend to tests.**

The PRD's module sketch anticipated "IPHost input, display, and filter handling (frontend, extends):
reads the declaration and suppresses the prefix control and mask rendering." Research shows there is
nothing to suppress:

- `frontend/app/src/entities/schema/domain/model/attribute-kind.ts:18` — `IP_HOST: "IPHost"` exists in
  the kind constant list and in `ATTRIBUTE_KINDS_FOR_LIST_VIEW`.
- `IP_HOST` / `IP_NETWORK` appear **nowhere** in the form-field dispatch
  (`src/shared/components/form/utils/getFormFieldFromAttribute.ts`), the table cell
  (`src/entities/nodes/object/ui/object-table/cells/table-attribute-cell.tsx`), the filter input
  (`src/entities/nodes/object/ui/filters/dynamic-filter-input.tsx`), or the form field types. Verified
  by grep across all five files: zero matches.
- `getFormFieldFromAttribute.ts:196` — an `IPHost` attribute falls through every kind branch and
  returns `basicFormFieldProps`, i.e. a plain text input.
- `prefixlen` / `prefixLength` appear nowhere in `frontend/app/src` outside generated types.

**Consequences**:

- **FR-010 is already satisfied by construction.** There is no prefix-length control on any `IPHost`
  edit form today. The requirement is met; what it needs is a **regression test** that pins the
  absence, not new code.
- **The UI half of FR-005 is free.** The UI renders the raw `value` string, so it displays a bare
  address as soon as the backend stores one.
- **Filters need no frontend change.** The filter input is a generic string field, so `__value`
  equality naturally carries bare input.

The plan therefore assigns the frontend **test-only** work and states this explicitly rather than
inventing components. If a future change adds a dedicated IPHost input with a prefix control, the
regression test added here is what will catch the resulting FR-010 violation.

**Risk accepted**: the E2E scenario in the spec's Testing Strategy still applies and is still worth
having, because it is the only test that proves the whole chain (schema → store → GraphQL → UI render)
end to end.

## R7 — SDK: the bare-address type already exists, and the dead path becomes the live one

**Decision**: branch on the flag in two places, reusing the `IPAddress` protocol types and the
`ip_address` mapper that SDK PR #1190 already merged.

**Rationale** — the already-merged residue the PRD flagged is not just dead weight, it is exactly the
machinery this feature needs:

- `python_sdk/infrahub_sdk/node/attribute.py:111-118` — the value coercion `value_mapper` maps
  `"IPHost": ipaddress.ip_interface`, `"IPNetwork": ipaddress.ip_network`, and **already**
  `"IPAddress": ipaddress.ip_address`. The `IPAddress` entry is currently unreachable: no `IPAddress`
  attribute kind exists in the backend, so `schema.kind` is never `"IPAddress"`.
- `python_sdk/infrahub_sdk/protocols_base.py:143-148` — `IPAddress` and `IPAddressOptional` protocol
  classes already exist with `value: ipaddress.IPv4Address | ipaddress.IPv6Address`. This is precisely
  the "bare address object" FR-011 asks for.
- `python_sdk/infrahub_sdk/protocols_generator/constants.py:18,20` — `ATTRIBUTE_KIND_MAP` already
  carries both `"IPHost": "IPHost"` and `"IPAddress": "IPAddress"`.
- `python_sdk/infrahub_sdk/protocols_generator/template.j2:30-35` already imports `IPHost`,
  `IPHostOptional`, `IPAddress`, `IPAddressOptional`.
- `python_sdk/infrahub_sdk/protocols_generator/generator.py:117-124` —
  `_jinja2_filter_render_attribute(value: AttributeSchemaAPI) -> str` receives the **whole**
  `AttributeSchemaAPI` and already branches on `value.optional` / `value.default_value`, so it can
  branch on `value.parameters`.
- `python_sdk/infrahub_sdk/schema/main.py:149` — `AttributeSchemaAPI.parameters` is
  `dict[str, Any] | None`. Confirmed: the flag reaches both the generator and the runtime coercion
  through an existing contract, so **FR-013 needs no SDK-side contract change**.

**Resolution of the open question about the dead path**: rather than deleting the `IPAddress` mapper
entry and the `IPAddress` protocol classes, this feature **repurposes** them as the flagged-`IPHost`
target. The kind-keyed `value_mapper` lookup is replaced by a lookup that consults the parameters for
`IPHost`, and the now-unreachable `"IPAddress"` *kind* key is what gets removed. Net effect: the
already-merged SDK work stops being dead without a second `IPAddress` concept existing anywhere.

**Correction to the brief**: the brief said the SDK needs no schema-API change because `parameters` is
a permissive dict. That is true for the runtime models, but `python_sdk/infrahub_sdk/schema/generated/read.py`
(lines 245-285) now carries **typed per-kind parameters read models** —
`TextAttributeParametersRead`, `NumberAttributeParametersRead`, `ListAttributeParametersRead`,
`NumberPoolParametersRead` — plus per-kind attribute-schema read classes. Regenerating after the
backend change will add `IPHostAttributeParametersRead` and an `IPHost` attribute-schema read class.
These are **generated**, not hand-written, but they are what the CI no-diff check spanning the
submodule will compare, and they are why the SDK change must land upstream before the pointer moves.

## R8 — Resolved: canonical bare form for IPv6

**Decision**: `str(ip_interface(value).ip)`.

**Rationale**: `ipaddress`'s `__str__` for `IPv4Address`/`IPv6Address` is the RFC 5952 canonical
form — compressed, lowercase, with the longest zero-run collapsed. This is byte-identical to what
today's undeclared path produces minus the mask, because
`ip_interface(v).with_prefixlen` is `f"{self.ip}/{self.network.prefixlen}"` over the same `ip` object.
IPv4-mapped addresses keep `ipaddress`'s own rendering. Host-bit normalisation cannot arise: only
`/32` and `/128` are accepted, so no host bits exist to mask off.

**Alternatives considered**: expanded form, or a bespoke canonicaliser. Both rejected — they would
introduce a second normalisation vocabulary and make declared and undeclared attributes differ in more
than the mask, which multiplies the FR-012 regression surface for zero user benefit.

## R9 — Resolved: filter semantics

**Decision**: leave every filter available and unchanged.

**Rationale**: R3 keeps `prefixlen` populated, so the `prefixlen` filter
(`core/query/attribute.py:429`) keeps resolving and returns the derived host length. `__value`
equality matches bare input because the stored value is bare. Suppressing the prefix filter per
attribute would mean threading schema parameters into `default_attribute_query_filter` and building
per-attribute filter-visibility machinery that does not exist — a Principle VII cost for no user gain,
and a risk of silently excluding flagged rows.

**Accepted residual**: a `prefixlen` filter on a field declared to have no prefix is coherent but
arguably surprising. Documented as an edge case in the spec, not fixed here.

## R10 — Value-vertex identity: no cross-kind collision

**Verified**: the write path does `MERGE (av:<labels> { <all to_db() props> })`
(`backend/infrahub/core/query/attribute.py:65-78`) and the label set differs by attribute type. A
flagged `IPHost` holding `10.0.0.1` writes labels including `AttributeIPHost` plus
`version`/`binary_address`/`prefixlen`; a `Text` attribute holding `"10.0.0.1"` writes different
labels and a different property map. Different vertex. The spec's edge case holds with no work.

The corollary is real and worth recording: a flagged attribute holding `10.0.0.1` is distinguishable
from an unflagged one holding `10.0.0.1/32` **only** by the `value` string. Any future feature needing
to tell them apart at the storage layer must read the schema, not the value vertex.

## Summary of open questions at Phase 0 exit

None. The spec's three carried-over questions are resolved at R8 (IPv6 form), R9 (filters), and R7
(the in-flight SDK residue, resolved by repurposing rather than deleting). No `NEEDS CLARIFICATION`
markers remain in the Technical Context.
