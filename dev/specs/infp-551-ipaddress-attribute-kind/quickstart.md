# Quickstart / Validation Guide: IPAddress attribute kind

End-to-end validation that the feature works across backend, GraphQL, UI, and SDK. Run
after implementation. This is a run/validation guide, not implementation detail.

## Prerequisites

- Infrahub running from this branch (`ipaddress-attribute-kind-infp-551`) with the backend
  changes applied.
- The `python_sdk` submodule pointing at the local SDK branch that carries the SDK changes
  (for the SDK checks in step 5).
- A schema that defines an attribute of `kind: IPAddress`, e.g. a node `TestDevice` with:
  - `primary_address` — `kind: IPAddress` (required)
  - `mgmt_host` — `kind: IPHost` (for the no-regression check)
  - `mgmt_net` — `kind: IPNetwork` (for the no-regression check)

## Backend / test-level validation (no running stack)

```bash
uv run invoke backend.generate          # regenerate schema/protocols; must be clean
uv run pytest backend/tests/unit/test_types.py -k IPAddress -q
uv run pytest backend/tests/component/core/test_attribute.py -k "IPAddress or IPHost or IPNetwork" -q
uv run pytest backend/tests/component/core/migrations/graph -k 075 -q
```

Expected: new IPAddress unit/component tests pass; IPHost/IPNetwork tests still pass.

## Scenario 1 — Store & read a bare address (FR-001/005/006)

1. Load the schema above.
2. Create a `TestDevice` with `primary_address = "192.0.2.10"`.
3. **GraphQL** query the device's `primary_address { value version }`.
   - Expect `value == "192.0.2.10"`, `version == 4`. No `/32`. No `prefixlen` field exists.
4. Repeat with IPv6 `2001:db8::1` → `value == "2001:db8::1"`, `version == 6`, no `/128`.

## Scenario 2 — Reject prefix notation (FR-003/004)

1. Attempt to create/update `primary_address = "192.0.2.10/24"`.
   - Expect a validation error identifying the value as not a valid `IPAddress`.
2. Attempt `"192.0.2.10/32"` and `"2001:db8::1/128"` → both rejected.
3. Attempt `"not-an-ip"` / `"999.0.0.1"` → rejected.
4. Attempt `"192.0.2.10"` → accepted.

## Scenario 3 — Web UI (FR-008)

1. In the UI, add/edit a `TestDevice`.
2. The `primary_address` field is a plain text input with **no** prefix-length selector.
3. Enter `192.0.2.10`; save. The detail view and the object table both show `192.0.2.10`
   with no mask. The display label / first column shows the bare address.

## Scenario 4 — HFID round-trip (FR-007)

1. Make `primary_address` part of the node's `human_friendly_id`.
2. Query the device; capture the returned HFID.
3. Look the device up again using that HFID verbatim.
   - Expect success with no need to add/remove a mask (the infrahub#8896 failure must not
     occur for IPAddress).

## Scenario 5 — SDK round-trip + no regression (FR-006/009/010, SC-002/004)

With the SDK changes and a running instance:

```python
import ipaddress
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync(address="http://localhost:8000")

dev = client.create("TestDevice", primary_address="192.0.2.10",
                    mgmt_host="10.0.0.5/24", mgmt_net="10.0.0.0/24", name="d1")
dev.save()

got = client.get("TestDevice", name__value="d1")
assert got.primary_address.value == ipaddress.ip_address("192.0.2.10")   # bare, no prefix
assert str(got.primary_address.value) == "192.0.2.10"
# no regression:
assert got.mgmt_host.value == ipaddress.ip_interface("10.0.0.5/24")       # keeps prefix
assert got.mgmt_net.value == ipaddress.ip_network("10.0.0.0/24")          # keeps prefix
```

Expected: the IPAddress value is a bare address object matching the UI and GraphQL; IPHost
and IPNetwork still return their prefixed interface/network objects.

## Scenario 6 — Filtering (FR-011)

1. Create several devices with distinct `primary_address` values.
2. GraphQL/SDK filter `primary_address__value == "192.0.2.10"`.
   - Expect only the matching device(s).

## Upgrade check (SC-005)

1. Start from a DB created before this change; upgrade to this build.
2. Confirm the `attr_ipaddress_bin` index exists and IPAddress works immediately with no
   manual DB steps (index is created on server startup and/or by the graph migration).

## Full gate before PR

```bash
uv run invoke format lint
uv run invoke backend.generate && git diff --exit-code   # generated files committed
cd frontend/app && pnpm biome:fix && pnpm codegen && pnpm test
# then /pre-ci
```
