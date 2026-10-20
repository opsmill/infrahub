# Data Model: Number pool body for pools without an allocation scope

**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md) | **Date**: 2026-10-08

The body stores nothing. It reads two query results and maps them to the domain types below, all in `entities/resource-manager/domain/model/number-pool.ts`, next to `NumberPoolData`. Field sources refer to the SDL in [PR #10932](https://github.com/opsmill/infrahub/pull/10932). Every `BigInt` field is converted to `number` in the mappers (research R2).

## `NumberPoolUsage`

How full one space is: the pool, or one range.

| Field | Type | Source (`NumberPoolUtilizationFigures`) | Meaning |
|---|---|---|---|
| `size` | `number` | `size` | Count of numbers the space holds, after the attribute's limits and excluded values. 0 when the pool has no range. |
| `used` | `number` | `used` | Distinct numbers held on any live branch |
| `usedDefaultBranch` | `number` | `used_default_branch` | Distinct numbers held on the default branch |
| `usedBranches` | `number` | `used_branches` | Distinct numbers held on other branches and not on the default branch |
| `utilization` | `number` | `utilization` | `used` as a percentage of `size`; 0 when `size` is 0 |

Invariant from the contract: `used = usedDefaultBranch + usedBranches`.

## `NumberPoolRange`

One range of the pool. A range is a node (`CoreNumberPoolRange`), so the type extends `NodeCore` and wraps its attributes in `NodeAttribute`, like `NumberPoolData`.

| Field | Type | Source (`NumberPoolRangeUtilization`) | Meaning |
|---|---|---|---|
| `id` | `string` | `id` | The range node's ID; the `:rangeId` in the address |
| `__typename` | `typeof NUMBER_POOL_RANGE_KIND` | set by the mapper | `"CoreNumberPoolRange"`; the query's own type name is `NumberPoolRangeUtilization` |
| `start` | `NodeAttribute<number>` | `start` | First number, included |
| `end` | `NodeAttribute<number>` | `end` | Last number, included |
| `allocation_weight` | `NodeAttribute<number>` | `weight` | Allocation weight; 0 when the range declares none |
| `usage` | `NumberPoolUsage` | `figures` | How full this range is |

`display_label` is not mapped: the page builds "<start> – <end>" itself (research R9).

## `NumberPoolUtilization`

Result of `getNumberPoolUtilization`.

| Field | Type | Source (`NumberPoolUtilization`) | Meaning |
|---|---|---|---|
| `usage` | `NumberPoolUsage` | `figures` | How full the whole pool is: the "All ranges" row |
| `ranges` | `NumberPoolRange[]` | `ranges` | Ranges in **fill order**: the use-case sorts them with `sortRangesByFillOrder` (research R8) |

## `NumberPoolAllocation`

One number held by one node on one branch. The allocation is not a node, so it stays a plain interface; its holder is a node.

| Field | Type | Source (`NumberPoolAllocation`) | Meaning |
|---|---|---|---|
| `value` | `number` | `value` | The number |
| `branch` | `string` | `branch` | Branch on which the holder's attribute holds it |
| `holder` | `NodeCore` | `holder.id`, `holder.kind` (as `__typename`), `holder.display_label` | The node that holds the number |
| `provenance` | `NumberPoolProvenance` | `provenance` | How the number got there |
| `rangeId` | `string` | `range.id` | The range that holds it, for the Range column |

`NumberPoolProvenance = typeof NUMBER_POOL_PROVENANCE_ALLOCATED | typeof NUMBER_POOL_PROVENANCE_PROVIDED`, with the constants `"ALLOCATED"` and `"PROVIDED"` declared in the same file. The Source column shows them as "Allocated" and "Provided".

**Range bounds**: `NumberPoolRangeRef` returns only `id` and `display_label`. The Range column shows "<start> – <end>" from the `NumberPoolRange` list the page already holds, looked up by `rangeId`.

`identifier` and `holder.hfid` are not mapped: no column shows them.

## `GetNumberPoolAllocationsResult`

Result of one page. File: `domain/use-cases/get-number-pool-allocations.ts`.

| Field | Type | Source |
|---|---|---|
| `allocations` | `NumberPoolAllocation[]` | `allocations` |
| `count` | `number` | `count`: rows matching the filters, before `offset` and `limit` |

## Use-case parameters

| Use-case | Params | Notes |
|---|---|---|
| `getNumberPoolUtilization` | `{ poolId, branchName, atDate? }` (extends `ContextParams`) | No `division` (scoped pools are out of scope) |
| `getNumberPoolAllocations` | `{ poolId, rangeId?, offset, limit, branchName, atDate? }` | `rangeId` undefined means every range. `limit` comes from `ui/queries` (research R5) |

Both use-cases throw on GraphQL `errors`, joining the messages, as `getNumberPool` does.

## Rules

| Rule | File | Behaviour |
|---|---|---|
| `sortRangesByFillOrder(ranges)` | `domain/rules/sort-ranges-by-fill-order.ts` | Returns a new array: higher `allocation_weight` first, then lower `start`, then lower `end`. Does not modify its input. |

## States the page derives (not stored)

| State | Condition | Shown (spec FR-016) |
|---|---|---|
| No ranges | `utilization.ranges.length === 0` | "No ranges" + hint by `pool_type` |
| All ranges selected | no `rangeId` in the address | "All ranges" highlighted; table with every range |
| One range selected | `rangeId` matches a range | That range highlighted; table for that range |
| Unknown range | `rangeId` set, no matching range | "This range is not part of the pool" + link; no allocations request |
| No numbers | allocations `count === 0` | "No allocations yet" or "No allocations in <range>" |
| Range column visible | "All ranges" selected and `ranges.length > 1` | Extra column |
