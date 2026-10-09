# Pinned stale processor reproduction

Use Node 24 or later with `stripTypeScriptTypes`, plus authenticated read-only GitHub CLI access.
The fixture executes downloaded upstream processor/date/state method bodies and supplies fake APIs,
loggers, and unrelated exemption helpers. It performs no GitHub writes and installs no packages.

From the repository root:

```bash
mkdir -p /tmp/ifc-3240-stale-source
gh api 'repos/actions/stale/contents/src/classes/issues-processor.ts?ref=4391f3da665fdf50b6810c1a66712fb9ba21aa93' -H 'Accept: application/vnd.github.raw+json' > /tmp/ifc-3240-stale-source/infrahub-stale-processor.ts
gh api 'repos/actions/stale/contents/src/functions/dates/is-date-more-recent-than.ts?ref=4391f3da665fdf50b6810c1a66712fb9ba21aa93' -H 'Accept: application/vnd.github.raw+json' > /tmp/ifc-3240-stale-source/infrahub-stale-date.ts
gh api 'repos/actions/stale/contents/src/classes/state/state.ts?ref=4391f3da665fdf50b6810c1a66712fb9ba21aa93' -H 'Accept: application/vnd.github.raw+json' > /tmp/ifc-3240-stale-source/infrahub-stale-state.ts
STALE_SOURCE_DIR=/tmp/ifc-3240-stale-source node dev/specs/005-pr-lifecycle/evidence/stale-repro.mjs
```

Expected: 26 assertions pass. The exact source SHA-256 hashes are:

| File | SHA-256 |
| --- | --- |
| infrahub-stale-processor.ts | 9545917e652b88e06a64c8c9c10645b25cba5659a91901ef5981a2a227c920d1 |
| infrahub-stale-date.ts | f4bbd5da44a0ecf45795729181436c17bc16ded2d991706397f892d7c05d1070 |
| infrahub-stale-state.ts | 3c5f33059183508162d0b6a67b8edae37dfa953d3fad5883c8f4c4965fc52cdb |

The fixture verifies these hashes before execution. Sources remain separately downloaded under
upstream licensing; no source files are vendored here. This is a planning experiment, not the final
companion test suite. Cache transport, real event emission, live token permissions, mutable GitHub
pagination, and concurrent mutation behavior still require broader integration tests.
