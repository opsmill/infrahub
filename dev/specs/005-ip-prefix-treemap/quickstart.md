# Quickstart: validating the IP Prefix Tree Map

**Date**: 2026-10-03 | **Spec**: [spec.md](spec.md) | **Contracts**: [contracts/](contracts/)

Runnable checks that prove the feature end to end. Implementation detail lives in `tasks.md`.

## Prerequisites

- Python and frontend dependencies installed (`uv sync --all-groups`, `cd frontend/app && pnpm install`).
- Docker running for the E2E stack.
- For manual checks, a running Infrahub with the demo data loaded, or the public sandbox at
  `https://sandbox.infrahub.app`.

## 1. Unit tests for the domain rules

```bash
cd frontend/app && pnpm test -- src/entities/ipam/ip-prefixes/domain
```

Expected: tests for `parse-prefix-length`, `build-tree-map-tiles` and `layout-tree-map` pass,
including the IPv6 cases (a /48 and a /64 inside a /32, a /128 inside a /32) and the capped
remainder case.

## 2. Component tests for the tiles and the empty state

```bash
cd frontend/app && pnpm test -- src/entities/ipam/ip-prefixes/ui
```

Expected: the allocated tile renders fills of 0, 50 and 100 percent; the free tile is disabled with
the permission message when create is not allowed; the address-type empty state shows the meter and
the IP Addresses link.

## 3. End-to-end

```bash
uv run invoke dev.build
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/ipam/test_ip_prefix_tree_map.py -s --pdb
```

The two variables make testcontainers run the image just built from this branch instead of a
published one.

Expected, against the `data_ipam_pools` slice:

1. Opening `/ipam`, clicking `10.0.0.0/8`, then the **Tree Map** link shows three allocated links
   named `10.0.0.0/16`, `10.1.0.0/16` and `10.2.0.0/16` and a free button named
   `10.3.0.0/16 available`.
2. Clicking the `10.1.0.0/16` tile lands on a page whose heading is `10.1.0.0/16` with the Tree Map
   tab active and the `namespace` query param unchanged.
3. Opening `10.0.0.0/16` (member type address) shows the empty state with the meter and the
   **IP Addresses** link.
4. On a throwaway branch, clicking a free tile opens the create form prefilled with its CIDR;
   saving closes the form and the same CIDR now appears as an allocated link without a reload.

## 4. Manual visual check

Open the Tree Map tab on `10.0.0.0/8` and on `2001:db8::/100` in both light and dark themes.
Confirm:

- Free tiles read as empty (dashed border, muted background) and allocated tiles carry a visible
  inner fill.
- No fixed palette colours: toggle the theme and check every tile re-colours.
- Labels disappear on tiles too small to hold them; the tooltip still shows the CIDR.

## 5. Performance measurement for SC-001

On a stack with the demo data, create a /16 with 256 direct /24 children on a branch (the SDK's
`allocate_next_ip_prefix` in a loop against a prefix pool is the quickest way), open its Tree Map
tab, and record the time from navigation to the last tile painted using the browser performance
panel. Repeat three times warm.

Record the result here:

| Date | Children | Median render time | Pass (under 3 s) |
|------|----------|--------------------|------------------|
| 2026-10-04 | 256 | 1.86 s (warm median of 3 runs; cold first load 3.90 s) | yes |

Measured on a dev-stack build of this branch with the `infrahub-demo-dc` data loaded: a throwaway
branch with 10.200.0.0/16 holding 256 direct /24 children, timed from navigation to the first tile
painted with Playwright, logged in as admin.

If it fails, the follow-up is a batched utilisation lookup raised as its own gated change, not an
amendment to this feature.

## 6. Lint and generated-file gates before pushing

```bash
set -e
(cd frontend && pnpm exec biome ci .)
(cd frontend/app && pnpm knip)
(cd frontend/app && pnpm exec betterer ci)
uv run ruff check tests/e2e && uv run ruff format tests/e2e
```

Then run `/pre-ci` for the full local gate, including `docs.validate`.
