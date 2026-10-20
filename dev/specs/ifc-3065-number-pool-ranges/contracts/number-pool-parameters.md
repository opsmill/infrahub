# Contract: NumberPool attribute parameters (published schema, ADR 0010)

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md)

## Declaration shapes accepted

```yaml
# Shorthand (deprecated, still supported)
- name: vlan_id
  kind: NumberPool
  parameters:
    start_range: 100
    end_range: 200

# Explicit ranges
- name: vlan_id
  kind: NumberPool
  parameters:
    ranges:
      - {start: 100, end: 200, weight: 10}
      - {start: 205, end: 300}

# Zero ranges (legal; the pool reports itself full)
- name: vlan_id
  kind: NumberPool
```

| Declaration | Outcome |
|-------------|---------|
| shorthand and `ranges` | refused at schema load: conflicting spellings |
| only `start_range` | end resolves to `sys.maxsize` |
| only `end_range` | start resolves to `1` |
| `start > end` on any range | refused |
| overlapping ranges | refused, clashing ranges named |
| shorthand present | load succeeds with one `DEPRECATION` warning per attribute, pointing at `parameters.ranges` |

## Generated contract changes

| Artifact | Change |
|----------|--------|
| `NumberPoolParametersWrite` / `Read` (SDK, openapi, frontend REST types) | `start_range`, `end_range` optional, default absent, description marks them deprecated; new `ranges: list[NumberPoolRangeWrite/Read]` |
| `NumberPoolRangeWrite` / `Read` (new family) | `start: int`, `end: int`, `weight: int \| None` |
| `READ_ONLY_FIELDS` | `NumberPoolRangeWrite` entry with the standard read-only set |
| Write JSON schema | `start_range`, `end_range` marked `deprecated: true` with a message pointing at `ranges` |
| `docs/docs/snippets/attribute-kind-params.mdx` | regenerated; absent defaults rendered as blank, not `None` |
| `backend/infrahub/core/protocols.py`, `python_sdk/infrahub_sdk/protocols.py` | `CoreNumberPool.start_range` / `end_range` optional; `ranges`; new `CoreNumberPoolRange` protocol |

## Schema-change validation

| Changed parameter | Constraint identifier | Validator |
|-------------------|-----------------------|-----------|
| `start_range` | `attribute.parameters.start_range.update` (existing) | `AttributeNumberPoolChecker` over the effective range set |
| `end_range` | `attribute.parameters.end_range.update` (existing) | same |
| `ranges` | `attribute.parameters.ranges.update` (new) | same |

The checker refuses the change when any object holds a value outside every effective range and lists those objects. Zero declared ranges with held values is refused.

## Ordering of the two repositories

1. PR on `opsmill/infrahub-sdk-python` (branch `stable`) with the regenerated SDK models.
2. Once merged, bump the `python_sdk` submodule pointer in the Infrahub PR.
