# Quickstart: validating bare IP addresses on IPHost attributes

**Feature**: `specs/infp-551-bare-ip-attribute` | **Date**: 2026-07-28

Runnable scenarios that prove the feature works. See [contracts/schema-contract.md](./contracts/schema-contract.md)
for the full accept/reject matrix and [data-model.md](./data-model.md) for the type changes.

## Prerequisites

```bash
uv sync --all-groups                    # Python deps
cd frontend/app && pnpm install         # Frontend deps
```

Component tests need a database. Either let testcontainers start one (requires a running Docker
daemon) or reuse the local dependency containers — the backing services are enough, no Infrahub
server or built image is required:

```bash
uv run invoke dev.deps                  # database, cache, message queue, task manager
INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest backend/tests/component/...
```

The integration scenarios additionally need the task manager to answer on `localhost:4200`.

## Test schema fixture

Every scenario below relies on one node kind carrying **both** flavours, because the primary risk is
regressing the undeclared path. The backend tests import it from
`backend/tests/helpers/schema/dns_record.py`; the equivalent payload for a running server is:

```yaml
version: "1.0"
nodes:
  - name: DnsRecord
    namespace: Testing
    label: DNS Record
    display_label: dns_target__value
    human_friendly_id: [dns_target__value]
    attributes:
      - name: dns_target          # the feature under test
        kind: IPHost
        unique: true
        parameters:
          allow_prefix: false
      - name: mgmt_ip             # control — must not change behaviour
        kind: IPHost
        optional: true
      - name: v6_target
        kind: IPHost
        optional: true
        parameters:
          allow_prefix: false
```

## Scenario 1 — Accept, reject, normalise (FR-003, FR-004)

```bash
INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest \
  "backend/tests/component/core/test_attribute_iphost_allow_prefix.py::TestValueValidationAndNormalisation" -v
```

Expected:

| Input on `dns_target` / `v6_target` | Outcome |
|-------------------------------------|---------|
| `10.0.0.1` | stored `10.0.0.1` |
| `10.0.0.1/32` | stored `10.0.0.1` |
| `2001:db8::1/128` | stored `2001:db8::1` |
| `10.0.0.1/24`, `10.0.0.1/31`, `10.0.0.1/0`, `2001:db8::1/64`, `2001:db8::1/127` | `ValidationError` naming the attribute |
| `10.0.0.1/128` | rejected as malformed, the same as today |

On the undeclared `mgmt_ip`, today's behaviour is unchanged: `10.0.0.1` is stored `10.0.0.1/32`, and
`/24`, `/31`, `/0` are all kept verbatim.

## Scenario 2 — Schema-load guards (FR-001, FR-002)

```bash
uv run pytest backend/tests/unit/core/schema/test_iphost_attribute_parameters.py -v
```

Expected: the fixture above loads. `allow_prefix: false` on a `Text` attribute fails to load.
`IPHostAttributeParameters` attached to a non-`IPHost` kind raises
`"IPHostAttributeParameters can't be used as parameters for {kind}"`. A bare `kind: IPHost` with no
`parameters` block yields `allow_prefix is True`.

Also expected, for declared default values:

| Declared `default_value` on a flagged attribute | Outcome |
|------------------------------------------------|---------|
| `10.0.0.1` | loads; schema records `10.0.0.1` |
| `10.0.0.1/32` | loads; schema records `10.0.0.1` (mask normalised away) |
| `10.0.0.1/24` | kept verbatim on the model, then **rejected when the schema is processed** |

The rejection happens at schema load, not at first node creation, because
`validate_default_values()` routes defaults through the same format validator — building the
`NodeSchema` alone leaves the value untouched, which is what the unit case pins. Against a running
server the load is refused with
`TestingDefaultCheck: default value 10.0.0.1/24 is not a valid IPHost because a subnet prefix is not permitted at target`.
A node created with no explicit value receives the bare default.

## Scenario 3 — Read surfaces, HFID round trip, uniqueness (FR-005, FR-006, FR-007, FR-008)

```bash
INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest \
  backend/tests/component/core/test_attribute_iphost_allow_prefix.py \
  backend/tests/component/graphql/queries/test_hfid.py -v
```

Expected, for a node created with `dns_target = "10.0.0.1/32"`:

- Stored value, GraphQL `value`, `display_label`, and `hfid` are all `10.0.0.1`.
- The `hfid` returned by a query is accepted verbatim as lookup input and resolves the same node,
  with zero caller-side transformation.
- `prefixlen` is `32` on the value vertex, and an IPAM prefix-containment query for `10.0.0.0/8`
  still returns the node.
- A second node created with `dns_target = "10.0.0.1"` violates the uniqueness constraint.
- `mgmt_ip` set to `10.0.0.1` still stores and returns `10.0.0.1/32`.

## Scenario 4 — Immutability (FR-009)

```bash
uv run pytest \
  "backend/tests/unit/core/schema/test_iphost_attribute_parameters.py::TestAllowPrefixDeclaration::test_allow_prefix_cannot_be_updated" -v
INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest \
  "backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py::TestAllowPrefixIsImmutable" -v
```

Load the fixture, then attempt a schema update flipping `allow_prefix` to `true`.

Expected: the update is refused as an unsupported change. Adding or removing the field on an existing
attribute is refused the same way, and a change to any other property of the same attribute is still
accepted. The rejected path carries `parameters.allow_prefix` as its property name; the message the
API renders drops it and reads
`'not_supported': TestingDnsRecord dns_target None`, listing one entry per changed attribute.

## Scenario 5 — Profiles, templates, branch merge (Principle II, spec edge cases)

Same component file — `TestGeneratedKindsInheritTheDeclaration`, `TestBranchMerge` and
`TestAttributeKindChange`. This is the highest-value group, because silent flag loss on an inherited
or profile path would look like the feature working.

Expected:

- A profile node for `TestingDnsRecord` validates and serialises `dns_target` identically to the node.
- A template node likewise.
- An attribute declared `allow_prefix: false` on a branch carries both the declaration **and** its
  rejection behaviour to the target branch after merge.
- Two branches setting `10.0.0.1` and `10.0.0.1/32` on the same flagged attribute produce **no** merge
  conflict — they converge on one stored value; two branches setting genuinely different addresses
  still conflict.
- Changing the attribute's kind away from `IPHost` silently drops the declaration — pinned as today's
  behaviour so a future change to it is deliberate (spec Out of Scope).

## Scenario 5b — Computed attributes and templates (spec edge case, Principle IV)

```bash
uv run invoke dev.build
uv run pytest backend/tests/integration_docker/test_computed_attributes.py -k bare_address -v
```

Constitution Principle IV requires Integration Docker coverage for features involving computed
attributes, so this scenario needs the full distributed stack rather than a component test. It runs
against the locally built image, so `dev.build` has to succeed first — see the local-environment
gotchas below.

Expected: a computed attribute that references a flagged attribute receives the **bare** value, and a
display-label Jinja2 template referencing it renders with no mask.

## Scenario 6 — Frontend regression (FR-010)

```bash
cd frontend/app && pnpm test getFormFieldFromAttribute
```

Expected: an `IPHost` attribute's form field carries no prefix-length control, whether or not
`allow_prefix` is set. This test pins behaviour that is currently true by construction — there is no
IPHost-specific input component today (see research.md R6). It exists so that a future dedicated
IPHost input cannot reintroduce a prefix control unnoticed.

## Scenario 7 — SDK value type and protocols (FR-011)

In the `python_sdk` submodule:

```bash
cd python_sdk
uv run pytest tests/unit/ -k "iphost or allow_prefix or protocols_generator" -v
```

Expected:

- A flagged attribute's `.value` is `IPv4Address` / `IPv6Address`.
- An undeclared `IPHost` attribute's `.value` is still `IPv4Interface` / `IPv6Interface`.
- Generated protocols annotate the flagged attribute `IPAddress` (or `IPAddressOptional`) and the
  undeclared one `IPHost` (or `IPHostOptional`).
- A schema payload with no `allow_prefix` key yields today's behaviour.

## Scenario 8 — End to end (spec E2E scenario)

```bash
cd frontend/app && pnpm test:e2e -- --grep "bare IP"
```

Expected: an operator creates a `TestingDnsRecord` entering `10.0.0.1/32`, and sees `10.0.0.1` in the
list view, the detail view, and the display label, with no prefix control anywhere in the form.
Fetching the same node through the SDK returns a bare address object.

## Generated artefacts gate

Run before pushing — CI fails on any stale generated file:

```bash
uv run invoke backend.generate
uv run invoke schema.generate-graphqlschema
uv run invoke schema.generate-jsonschema
uv run invoke docs.generate
cd frontend/app && pnpm codegen

uv run invoke docs.validate            # must be clean
```

Then the full local CI gate:

```bash
uv run invoke format lint
uv run invoke backend.test-unit
cd frontend/app && pnpm exec biome ci . && pnpm knip && pnpm exec betterer ci && pnpm test
```

Or in one step: `/pre-ci`.

## Known local-environment gotcha

This change produces a core-schema diff, so `infrahub upgrade` hits the known Prefect
flow-parameter size limit locally (the full schema exceeds the 512 KB flow-parameter cap). Work around
it on the host environment:

```bash
PREFECT_SERVER_API_MAX_PARAMETER_SIZE=0 uv run infrahub upgrade
```

This is an environment limit, not a defect in the feature.

## Manual smoke check

```bash
uv run invoke dev.start
# load the fixture schema, then:
```

```graphql
mutation {
  TestingDnsRecordCreate(data: { dns_target: { value: "10.0.0.1/32" } }) {
    ok
    object { dns_target { value prefixlen netmask } display_label hfid }
  }
}
```

Expect `value: "10.0.0.1"`, `prefixlen: 32`, `display_label: "10.0.0.1"`, `hfid: ["10.0.0.1"]`. Then
repeat with `"10.0.0.1/24"` and expect a validation error naming `dns_target`.
