# Phase 1 Data Model: Bare IP addresses on IPHost attributes

**Feature**: `specs/infp-551-bare-ip-attribute` | **Date**: 2026-07-28

Two new schema-layer types and two behaviour changes on an existing attribute class. **No graph
change of any kind.**

## New: `IPHostAttributeParameters`

Location: `backend/infrahub/core/schema/attribute_parameters.py`.
Base: `AttributeParameters` (which sets `model_config = ConfigDict(extra="forbid")`).

| Field | Type | Default | `update` classification | Meaning |
|-------|------|---------|------------------------|---------|
| `allow_prefix` | `bool` | `True` | `UpdateSupport.NOT_SUPPORTED` | When `True` (the default), the attribute behaves exactly as `IPHost` does today: values are canonicalised to `with_prefixlen`. When `False`, the attribute holds a bare address: values carrying a non-host subnet prefix are rejected, and stored values carry no mask. |

**Why the default is `True`**: it is the sole guarantee behind FR-012 and SC-006. Every existing
schema, and every schema that never mentions the field, parses to an instance whose behaviour is
byte-identical to the pre-feature path.

**Why `NOT_SUPPORTED`**: the schema-diff walker reads each parameter sub-field's own
`json_schema_extra["update"]` and emits `property_name = "parameters.allow_prefix"`
(`backend/infrahub/core/models.py:279-300`). This classification is the entire enforcement mechanism
for FR-009 and therefore for the feature's migration-free property. `NumberPoolParameters.number_pool_id`
is the live precedent.

**Registration**: `"IPHost": IPHostAttributeParameters` in `get_attribute_parameters_class_for_kind`.

## New: `IPHostAttributeSchema`

Location: `backend/infrahub/core/schema/attribute_schema.py`.
Base: `AttributeSchema`. Mirrors `TextAttributeSchema` / `NumberAttributeSchema` exactly.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `parameters` | `IPHostAttributeParameters` | `default_factory=IPHostAttributeParameters` | `json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value}`, matching the sibling per-kind schemas. The sub-field's own `NOT_SUPPORTED` wins for `allow_prefix` (see above). |

**Registration**: `"IPHost": IPHostAttributeSchema` in `attribute_schema_class_by_kind`.

Registering here has a second, free effect: `AttributeSchema.model_json_schema`
(`attribute_schema.py:53-69`) iterates `attribute_schema_class_by_kind` to emit `allOf` /
`if`-`then` conditional blocks, so YAML-language-server users editing a schema file get
`allow_prefix` completion on `kind: IPHost` and nowhere else.

## Changed: `AttributeSchema.validate_parameters`

One added branch, matching the three that exist:

```text
if isinstance(self.parameters, IPHostAttributeParameters) and self.kind != "IPHost":
    raise ValueError(f"IPHostAttributeParameters can't be used as parameters for {self.kind}")
```

This is the *reverse* guard, and it is the only direction that raises. The forward direction —
`allow_prefix` supplied as a plain mapping on a `Text` attribute — is **not** rejected: the mapping is
coerced to the attribute kind's own parameters model, and that coercion filters unknown keys out
before `extra="forbid"` can inspect them, so the flag is silently dropped. That is pre-existing
behaviour for every attribute parameter (`regex` on a `Number` attribute behaves the same way) and is
pinned by a test rather than changed here. FR-002 is therefore satisfied in the "unreachable on other
kinds" sense, not the "load fails" sense — see spec.md FR-002.

## Changed: internal schema registration

`backend/infrahub/core/schema/definitions/internal.py:803-817` — the `parameters` `SchemaAttribute`
carries `internal_kind` as a list of parameter classes, rendered as a `" | "`-joined union type
annotation on the generated schema (`internal.py:122-123`). `IPHostAttributeParameters` joins that
list.

This single edit is what produces the core-schema diff and the regenerated artefacts named in the
governance gate. The field already carries
`extra={"update": UpdateSupport.VALIDATE_CONSTRAINT, "visibility": Visibility.WRITE}`, so the new
class inherits publication at `WRITE` visibility — **FR-013 needs no additional work**.

## Changed: `IPHost` attribute behaviour

Location: `backend/infrahub/core/attribute.py`. Two methods, both of which already have the schema in
hand.

### `validate_format(cls, value, name, schema)` — `attribute.py:1131`

Existing behaviour retained in full: `super().validate_format(...)`, then `ipaddress.ip_interface(value)`
raising `ValidationError({name: f"{value} is not a valid {schema.kind}"})` on failure.

Added: when `allow_prefix` is `False` and the parsed interface's `network.prefixlen` is not the host
length for its version (`32` for IPv4, `128` for IPv6), raise `ValidationError` keyed by `name` with a
message stating that a subnet prefix is not permitted on this attribute.

Reading the flag: `getattr(schema.parameters, "allow_prefix", True)`. The defensive form is required,
not stylistic — this is a classmethod typed against the base `AttributeSchema`, and inherited, profile,
and template paths may hand it a base-classed instance whose `parameters` is a plain
`AttributeParameters`. Defaulting to `True` means the worst case is "flag ignored", never an
`AttributeError` at write time.

Note the check is on the **parsed prefix length**, not on the presence of a `/` in the input string.
That is what makes `10.0.0.1/32` accepted (FR-004) while `10.0.0.1/31` and `10.0.0.1/0` are refused.

### `_normalize_value(self, value)` — `attribute.py:1150`

| `allow_prefix` | Returns | Example |
|----------------|---------|---------|
| `True` (default) | `ipaddress.ip_interface(value).with_prefixlen` — unchanged | `10.0.0.1` → `10.0.0.1/32` |
| `False` | `str(ipaddress.ip_interface(value).ip)` | `10.0.0.1/32` → `10.0.0.1` |

This is an instance method and `self.schema` is set at `attribute.py:120`, before the
validate/normalise pair runs at `attribute.py:166-167`.

`IPHost` does not override `serialize_value`, so the normalised string **is** the stored value. That
single fact is why FR-005, FR-006, and FR-007 need no further code.

### Unchanged: derived properties and `to_db()`

`IPHost.obj` is `ipaddress.ip_interface(str(self.value))` (`attribute.py:1052-1062`). Given a bare
`10.0.0.1` it yields `IPv4Interface('10.0.0.1/32')`, so every derived property stays correct and
truthful:

| Property | Bare-stored `10.0.0.1` | Prefixed-stored `10.0.0.1/32` |
|----------|------------------------|-------------------------------|
| `ip` | `10.0.0.1` | `10.0.0.1` |
| `prefixlen` | `32` | `32` |
| `netmask` | `255.255.255.255` | `255.255.255.255` |
| `version` | `4` | `4` |
| `ip_binary` | identical | identical |
| `value` | **`10.0.0.1`** | **`10.0.0.1/32`** |

`to_db()` (`attribute.py:1158-1166`) is untouched: `version`, `binary_address`, and `prefixlen` are
still written. FR-008 therefore requires **no code change at all** — only a test asserting it, because
the requirement is that a plausible "clean up the now-meaningless prefixlen" refactor never happens.

## Graph storage: explicitly unchanged

| Aspect | Status |
|--------|--------|
| Value-node label set (`AttributeIPHost`, `AttributeValue`, …) | Unchanged for flagged and unflagged alike |
| Properties written (`value`, `is_default`, `binary_address`, `version`, `prefixlen`) | Unchanged |
| Indexes | None added, none removed |
| `GRAPH_VERSION` | Unchanged |
| Data migration | None |
| Stored values on existing attributes | Zero changed |

### Value-vertex identity consequences

The write path does `MERGE (av:<labels> { <all to_db() props> })`
(`backend/infrahub/core/query/attribute.py:65-78`). Three consequences, all intended:

1. **Convergence.** `10.0.0.1` and `10.0.0.1/32` on a flagged attribute produce the same `value` and
   therefore the same property map and the same vertex. They are indistinguishable after the write.
   FR-007's uniqueness collision is a *direct result* of this, not extra machinery.
2. **No merge conflict.** Branch diffs and conflict detection compare stored values, so two branches
   setting the two forms produce no conflict. Intended; must be asserted.
3. **No cross-kind collision.** A flagged `IPHost` holding `10.0.0.1` and a `Text` attribute holding
   `"10.0.0.1"` differ in label set and property map, so they are different vertices.

**Recorded corollary**: a flagged attribute holding `10.0.0.1` differs from an unflagged one holding
`10.0.0.1/32` **only** in the `value` string. Any future feature that must distinguish them at the
storage layer has to read the schema, not the value vertex.

## SDK model changes

Location: `python_sdk/` (separate repository). No new types — the needed ones already exist.

| Element | Current state | Change |
|---------|---------------|--------|
| `protocols_base.IPAddress` / `IPAddressOptional` | Already defined with `value: IPv4Address \| IPv6Address` (`protocols_base.py:143-148`); currently unreachable | Becomes the annotation emitted for flagged `IPHost` attributes |
| `node/attribute.py` `value_mapper` | Keyed by `schema.kind`; contains an unreachable `"IPAddress": ip_address` entry (`attribute.py:111-118`) | For `IPHost`, select `ip_address` vs `ip_interface` by consulting `schema.parameters`; drop the unreachable `"IPAddress"` kind key |
| `AttributeSchemaAPI.parameters` | Already `dict[str, Any] \| None` (`schema/main.py:149`) | **No change** — the flag reaches the SDK through this existing contract |
| `ATTRIBUTE_KIND_MAP`, `template.j2` imports | Already carry both `IPHost` and `IPAddress` | **No change** |
| `protocols.py`, `schema/generated/read.py` | — | Regenerated; `read.py` gains `IPHostAttributeParametersRead` |

Because the SDK reads `parameters` as a plain dict, the flag must be read with a dict access that
tolerates absence (`(schema.parameters or {}).get("allow_prefix", True)`), mirroring the backend's
defensive default.

## Frontend model changes

**None.** Research R6 established that `IPHost` has no dedicated input, table-cell, or filter handling
— it falls through to a plain text field at
`frontend/app/src/shared/components/form/utils/getFormFieldFromAttribute.ts:196`, and `prefixlen`
appears nowhere in `frontend/app/src` outside generated types. FR-010 is satisfied by construction and
the UI half of FR-005 follows from bare storage. The frontend contribution to this feature is a
regression test, not a model change.
