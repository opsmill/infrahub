# Contract: what the form sends for a pool-targeted Number attribute

Applies to a plain Number attribute with a `pool` and no `fromPoolRelationshipName`. Backend rows
refer to [`from-pool-intent.md`](../../ifc-3184-pool-number-attach/contracts/from-pool-intent.md).

`P` is the pool tracking the attribute when the form opens; `B` is another pool; `n` the current
number; `m` a number the user types.

| # | Form | Opens on | User action | Sent for the attribute | Backend row | Result |
|---|---|---|---|---|---|---|
| C1 | create | Value | types `m` | `{ value: m }` | 5 | number `m`, no pool |
| C2 | create | Value | pool tab, picks `B`, no number | `{ value: null, from_pool: { id: B } }` | 6 | next free number of `B` |
| C3 | create | Value | pool tab, picks `B`, types `m` | `{ value: m, from_pool: { id: B } }` | 1 | `m`, tracked by `B` |
| C4 | create | Value | pool tab, types `m`, no pool | not saved: "Select a pool" error | — | — |
| C5 | create | Value | visits pool tab, returns, saves | nothing | — | — |
| E1 | edit, untracked | Value | types `m` | `{ value: m }` | 5 | `m`, no pool |
| E2 | edit, untracked | Value | picks `B`, keeps `n` | `{ value: n, from_pool: { id: B } }` | 1 | `n`, tracked by `B` (adopt) |
| E3 | edit, untracked | Value | picks `B`, empties number | `{ value: null, from_pool: { id: B } }` | 6 | next free number of `B` |
| E4 | edit, tracked by `P` | From pool | nothing | nothing | — | unchanged |
| E5 | edit, tracked by `P` | From pool | changes number to `m` | `{ value: m, from_pool: { id: P } }` | 3 | `m`, tracked by `P` |
| E6 | edit, tracked by `P` | From pool | empties number | `{ value: null, from_pool: { id: P } }` | 7 | `n` kept (reserved) |
| E7 | edit, tracked by `P` | From pool | picks `B`, keeps `n` | `{ value: n, from_pool: { id: B } }` | 4 | `n`, tracked by `B` |
| E8 | edit, tracked by `P` | From pool | picks `B`, empties number | `{ value: null, from_pool: { id: B } }` | 8 | next free number of `B` |
| E9 | edit, tracked by `P` | From pool | Value tab, types `m` (or `n`) | `{ value: m, from_pool: null }` | 13 | `m`, no pool |
| E10 | edit, tracked by `P` | From pool | Value tab, returns without typing | nothing | — | unchanged |
| E11 | edit, tracked by `P` | From pool | Value tab, clears the number | `{ value: null, from_pool: null }` | 13 | empty, no pool |

Rows 10 and 12 of the backend table (`from_pool` without `value`) are never sent.

Template-backed fields (`fromPoolRelationshipName` set) and the `NumberPool` attribute kind are
unchanged and not covered by this table.
