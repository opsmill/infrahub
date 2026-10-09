# Data Model: Number attribute — set a number or take it from a number pool

Frontend form state only; no backend model change.

## Form value of a Number attribute

`FormAttributeValue` in `frontend/app/src/shared/components/form/type.ts`.

| State | `source` | `value` |
|---|---|---|
| Number typed in the Value tab | `{ type: "user" }` | `number \| null` |
| Pool staged in the pool tab | `NumberPoolSource` (`type: "pool"`, `kind: "CoreNumberPool"`, `id`, `label`) | `{ from_pool: { id, number?: number \| null } }` |
| Edit form, a number pool tracks the attribute | `NumberPoolSource` of the tracking pool | `{ from_pool: { id, number: <current number> } }` |
| Schema default | `{ type: "schema" }` | default number |
| Profile or template | as today | as today |

Change: `AttributeValueFromPool.value.from_pool` gains `number?: number | null`. It is meaningful
only when `source.kind === "CoreNumberPool"`.

## Field props

| Prop | Owner | Change |
|---|---|---|
| `pool: FormFieldPool` | `DynamicNumberFieldProps` | unchanged |
| `initialTab?: "value" \| "from-pool"` | `PoolBackedFieldProps` | new; defaults to `"value"` |

## State transitions (edit form, pool P tracks the attribute)

```text
open ──► pool tab {P, n}
pool tab {P, n}  ──edit number──►  {P, m}         save: value m + from_pool P   (attach, row 3)
pool tab {P, n}  ──pick B──────►   {B, n}         save: value n + from_pool B   (attach, row 4)
pool tab {B, n}  ──empty number─►  {B, null}      save: value null + from_pool B (allocate, row 8)
pool tab         ──Value tab───►   default {P, n} save: nothing
Value tab        ──type m──────►   user m         save: value m + from_pool null (detach, row 13)
```
