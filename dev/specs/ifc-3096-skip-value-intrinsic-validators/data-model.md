# Data Model: Stop emitting value-intrinsic constraint validators on data-only diffs

**Feature**: IFC-3096 | **Date**: 2026-08-31

**No persisted data changes.** No database schema change, no migration, no new node kind, no new stored property, no new configuration key. The only state this feature alters is a class attribute evaluated in memory during constraint determination.

This document therefore describes the **in-memory model** the feature operates on, and the classification it changes.

## Entities

### `ConstraintCheckerInterface` (`infrahub/core/validators/interface.py`)

The abstract base every constraint checker implements.

| Member | Type | Change |
|---|---|---|
| `triggered_by_data_change` | `bool`, class attribute, default `True` | **Unchanged.** The default stays `True` per FR-006: a forgotten declaration must be a wasted-work bug, never a silent under-validation bug. |
| `name` | abstract property, `str` | Unchanged |
| `supports(request)` | abstract, `bool` | Unchanged |
| `check(request)` | abstract, `list[GroupedDataPaths]` | Unchanged |

### Constraint checker implementations (`infrahub/core/validators/**`)

Nineteen concrete classes. Eight gain `triggered_by_data_change = False`; none change their `check` or `supports` logic.

**State transition** — the only one in this feature, per checker class:

```text
triggered_by_data_change = True  (inherited default)
        │
        └──► triggered_by_data_change = False  (explicit class attribute)
```

Classes transitioning:

`AttributeKindChecker`, `AttributeOptionalChecker`, `AttributeRegexChecker`, `AttributeLengthChecker`, `AttributeEnumChecker`, `AttributeChoicesChecker`, `AttributeNumberChecker`, `RelationshipPeerChecker`.

Classes already in the `False` state before this feature, unchanged: `NodeInheritFromChecker`, `NodeGenerateProfileChecker`.

### `CONSTRAINT_VALIDATOR_MAP` (`infrahub/core/validators/__init__.py`)

`dict[str, type[ConstraintCheckerInterface] | None]` — 29 entries mapping a constraint identifier to the checker class that guards it. Many-to-one: several identifiers share a checker.

**Change**: two keys normalised from `ConstraintIdentifier` members to `.value` strings (`attribute.parameters.start_range.update`, `attribute.parameters.end_range.update`), so all 29 keys are uniformly plain `str`. Behaviour-preserving — `ConstraintIdentifier` is a `StrEnum`, so member and value hash and compare identically. See research R4.

### `ConstraintValidatorDeterminer` (`infrahub/core/validators/determiner.py`)

**Unchanged.** Reads `triggered_by_data_change` at two points, both already present:

| Method | Scope | Guard |
|---|---|---|
| `_get_property_constraints_for_one_schema` | node-level properties (`node.<prop>.update`) | skip when the mapped checker declares `False` |
| `_get_constraints_for_one_field` | attribute and relationship field properties | skip when the mapped checker declares `False` |

### `MergeSchemaAnalyzer` (`infrahub/core/merge/schema_analyzer.py`)

**Unchanged.** `get_3ways_diff_schema` sums `common_ancestor → source` and `common_ancestor → destination`, so `calculate_validations` owns guarded-property changes originating on either branch. This is what FR-002 relies on.

### `ConstraintInfoMerger` (`infrahub/core/validators/constraint_merge.py`)

**Unchanged.** Unions the two producers' outputs with unrestricted scope winning, so removing entries from the data-diff producer leaves the schema-diff producer's entries intact at full scope.

## The classification

The feature's substantive content. Each row states the constraint family, the identifiers it covers, and why the classification holds.

### No data trigger — value-intrinsic

Enforced on every individual value at the moment it is written, so a data change cannot produce a violating value.

| Family | Identifiers | Why a data change cannot violate it |
|---|---|---|
| Attribute kind | `attribute.kind.update` | Every write coerces and validates the value against the attribute's kind |
| Attribute optionality | `attribute.optional.update` | Mandatory-ness is checked per write; a null cannot be persisted for a mandatory attribute |
| Attribute regex | `attribute.regex.update`, `attribute.parameters.regex.update` | The pattern is applied per value at write time |
| Attribute length | `attribute.min_length.update`, `attribute.max_length.update`, `attribute.parameters.min_length.update`, `attribute.parameters.max_length.update` | Bounds are applied per value at write time |
| Attribute enum | `attribute.enum.update` | Membership is checked per value at write time |
| Attribute dropdown choices | `attribute.choices.update` | Membership is checked per value at write time |
| Attribute numeric bounds | `attribute.parameters.min_value.update`, `attribute.parameters.max_value.update`, `attribute.parameters.excluded_values.update` | Bounds and exclusions applied per value at write time, under the same strict-validation setting that gates the merge-time checker |
| Relationship peer | `relationship.peer.update` | See the widening argument below |

Each "why" column entry has been **verified against the code** — see research R9 for the traced `file::symbol` per family. All eight families survived tracing, so this table is unchanged from the pre-tracing draft. The seven attribute families share one enforcement point, `core/attribute.py::BaseAttribute.validate`, reached on every attribute write including node update, where it re-runs for every attribute of the touched node.

**Relationship peer** reaches the conclusion differently and is the least obvious entry. Its effective allowed set is the declared peer kind plus, for a generic peer, the kinds using that generic. That list is derived from every node's inheritance declaration and never set directly. It can only:

- **grow** — widening the allowed set, which cannot invalidate an existing link; or
- **shrink** — which requires either removing a generic from a node's inheritance (rejected outright by the inheritance checker regardless of data) or deleting the kind entirely (which removes its instances with it).

Both halves are confirmed in R9: `used_by` is `update: not_applicable`, excluded from the schema diff, and written only by `SchemaBranch.process_inheritance`; `NodeInheritFromChecker.check` emits its violation from the schema comparison alone, running no data query. A write-time peer-kind check exists too (`RelationshipPeerKindConstraint`), but it is wired at the mutation/service layer rather than inside `Node.save()`, so it corroborates the argument rather than carrying it.

### Retains its data trigger — cross-node

Combining two independently-valid branches genuinely can produce a violation, because the constraint spans more than one node.

| Family | Identifiers |
|---|---|
| Attribute uniqueness | `attribute.unique.update` |
| Node uniqueness constraints | `node.uniqueness_constraints.update` |
| Node hierarchy | `node.parent.update`, `node.children.update` |
| Relationship cardinality and count | `relationship.cardinality.update`, `relationship.min_count.update`, `relationship.max_count.update` |
| Relationship optionality | `relationship.optional.update` |
| Relationship common parent | `relationship.common_parent.update` |
| Node attribute add | `node.attribute.add` |
| Node relationship add | `node.relationship.add` |
| Attribute number pool range | `attribute.parameters.start_range.update`, `attribute.parameters.end_range.update` — out of scope by decision, not by argument: enforcement lives in pool allocation and was not traced |

### Already classified, untouched

`node.inherit_from.update`, `node.generate_profile.update` — declared `False` before this feature.

## Invariants

1. **Totality** — every key in `CONSTRAINT_VALIDATOR_MAP` appears in exactly one of the three tables above. Enforced by the FR-004 pinning test asserting full dict equality over all 29 identifiers.
2. **Fail-safe direction** — a checker that states no classification is treated as data-triggerable. Enforced by the interface default staying `True` (FR-006), pinned by consequence through the 13 `True` entries in the expected literal.
3. **Producer independence** — a constraint removed from the data-diff producer's output remains schedulable at unrestricted scope by the schema-diff producer. Guaranteed by `ConstraintInfoMerger`'s union semantics; asserted by the FR-002 component test.
