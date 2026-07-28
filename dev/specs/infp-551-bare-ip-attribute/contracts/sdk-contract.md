# Contract: Python SDK surface

**Feature**: `specs/infp-551-bare-ip-attribute` | **Date**: 2026-07-28

Lives in the `infrahub-sdk-python` repository (the `python_sdk/` submodule). **No new public methods
and no new types** — the bare-address protocol types already exist. This change makes two existing
code paths read the schema parameter, which also retires the unreachable `IPAddress` code merged by
SDK PR #1190.

## Runtime value contract

`Attribute.value` for an `IPHost` attribute:

| Schema | Returned type | Example value |
|--------|---------------|---------------|
| `allow_prefix: false` | `ipaddress.IPv4Address` / `ipaddress.IPv6Address` | `IPv4Address('10.0.0.1')` |
| `allow_prefix: true` or absent | `ipaddress.IPv4Interface` / `ipaddress.IPv6Interface` | `IPv4Interface('10.0.0.1/32')` |

```python
node = await client.get(kind="TestingDnsRecord", id=...)

# declared allow_prefix: false
node.dns_target.value          # IPv4Address('10.0.0.1')
str(node.dns_target.value)     # "10.0.0.1"

# undeclared IPHost — unchanged from today
node.mgmt_ip.value             # IPv4Interface('10.0.0.1/32')
str(node.mgmt_ip.value)        # "10.0.0.1/32"
```

**Mechanism**: `node/attribute.py:111-118` currently selects a coercion callable by `schema.kind`. For
`IPHost` it must instead consult the parameters:

```text
IPHost + allow_prefix false  -> ipaddress.ip_address
IPHost + allow_prefix true   -> ipaddress.ip_interface   (unchanged)
IPNetwork                    -> ipaddress.ip_network     (unchanged)
anything else                -> identity                 (unchanged)
```

The flag is read from `AttributeSchemaAPI.parameters`, which is already `dict[str, Any] | None`
(`schema/main.py:149`). Read it tolerantly — `(schema.parameters or {}).get("allow_prefix", True)` —
so an older server that does not publish the field yields today's behaviour rather than an error.

**Removal**: the `"IPAddress"` key in `value_mapper` is unreachable (no such attribute kind exists on
the server) and is removed. This is the dead-path cleanup the PRD called for; the `ip_address`
callable it referenced is what the flagged `IPHost` branch now uses.

## Generated protocol contract

`_jinja2_filter_render_attribute` (`protocols_generator/generator.py:117-124`) emits:

| Schema | Emitted annotation |
|--------|-------------------|
| `IPHost`, `allow_prefix: false`, required | `IPAddress` |
| `IPHost`, `allow_prefix: false`, optional with no default | `IPAddressOptional` |
| `IPHost`, `allow_prefix: true`/absent, required | `IPHost` (unchanged) |
| `IPHost`, `allow_prefix: true`/absent, optional with no default | `IPHostOptional` (unchanged) |

```python
# generated protocol for a node with both attribute flavours
class TestingDnsRecord(CoreNode):
    dns_target: IPAddress          # allow_prefix: false
    mgmt_ip: IPHost                # undeclared — unchanged
    backup_target: IPAddressOptional
```

The existing `Optional` suffixing rule (`value.optional and value.default_value is None`) is unchanged
and composes with the new branch.

**Already in place, requiring no change**:

- `protocols_base.py:143-148` — `IPAddress` / `IPAddressOptional` with
  `value: ipaddress.IPv4Address | ipaddress.IPv6Address`
- `protocols_generator/constants.py:18,20` — `ATTRIBUTE_KIND_MAP` entries for both names
- `protocols_generator/template.j2:30-35` — imports for all four protocol classes

## Schema-read contract

No hand-written change. `AttributeSchemaAPI.parameters` already carries the flag.

Regenerating after the backend change adds `IPHostAttributeParametersRead` and an `IPHost`
attribute-schema read class to `schema/generated/read.py`, alongside the existing
`TextAttributeParametersRead` / `NumberAttributeParametersRead` / `ListAttributeParametersRead` /
`NumberPoolParametersRead` (`read.py:245-285`). These are generated files and are what the
CI no-diff check spanning the submodule compares.

## Cross-repo ordering

Root `AGENTS.md` § Submodules requires the pointed-to commit to be "merged **or the commit is
otherwise available upstream**". That yields two gates, not one, and they bind at different moments:

1. **Push gate — blocks the pointer bump.** The SDK commit must be pushed to `origin` in
   `infrahub-sdk-python` (branch `infrahub-develop` for Infrahub `develop`). A pushed PR branch
   satisfies this, so the `python_sdk` pointer may move provisionally and let Infrahub CI run against
   the real SDK change. **Merge is not required here** — blocking the pointer on the SDK merge would
   serialise two reviews that can safely run concurrently.
2. **Merge gate — blocks the *Infrahub* PR merge.** Once the SDK PR merges, re-point the submodule to
   the merged commit and verify it is an ancestor of `origin/infrahub-develop`
   (`git merge-base --is-ancestor`).

Gate 2 exists because a provisional pointer is safe for CI but not for `develop`: if the SDK PR is
squashed or rebased on merge and its branch deleted, the commit the pointer names is no longer
reachable and can eventually become unfetchable. An Infrahub commit on `develop` naming an orphaned
SDK commit breaks every fresh clone — which is the failure the submodule rule is actually guarding
against, and it is a property of *merge time*, not of pointer-bump time.

## Version skew

Both directions, stated explicitly — one is safe, the other is not:

| Combination | Behaviour | Safe? |
|-------------|-----------|-------|
| **New SDK, old server** (no `allow_prefix` published) | Tolerant read defaults to `True` → `ip_interface` → today's behaviour | ✅ Yes |
| **Old SDK, new server** (flagged attribute, bare stored value) | The SDK has no flag-aware branch and coerces `"10.0.0.1"` with `ip_interface`, yielding `IPv4Interface('10.0.0.1/32')` — **the host mask is re-attached** | ❌ No |

The second row is the contradiction FR-005 and FR-011 exist to prevent, and it is unavoidable for that
combination: an SDK that predates this change cannot know the value is meant to stay bare. Therefore:

> **Consuming a bare-address attribute requires an SDK at or above the version that ships this
> change.** Older SDKs silently re-attach the host mask.

This must appear in the user-facing documentation, not only here — a silent mask re-appearing in a
consumer is exactly the class of surprise this feature exists to remove.

## Backward-compatibility guarantees

1. An undeclared `IPHost` attribute returns `IPv4Interface`/`IPv6Interface` exactly as today.
2. A server that does not publish `allow_prefix` yields today's behaviour (tolerant read).
3. No public SDK method signature changes.
4. `IPHost` / `IPHostOptional` protocol classes are unchanged and still emitted for undeclared
   attributes.
5. The version floor above is the one deliberate exception: old SDK against new server is not
   backward-compatible for flagged attributes, by necessity.
