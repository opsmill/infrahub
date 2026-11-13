# Research: Number attribute — set a number or take it from a number pool

## R1. Where the existing tabs come from

- **Finding**: `fields/number.field.tsx::NumberField` already wraps the number input in
  `pool-backed-field.tsx::PoolBackedField`, and `utils/getFormFieldFromAttribute.ts` gives it a
  `pool` when a `CoreNumberPool` targets this kind and attribute (or a template
  `<name>_from_resource_pool` relationship exists). The pool list comes from
  `useGetNumberPools` in `form/node-form.tsx`, filtered by `node__values` (kind and inherited
  generics) and then by `attributeName`.
- **Decision**: Reuse as is. FR-001, FR-002 and FR-004 are already met; the work is the pool tab's
  number input, the payloads and the edit-mode state.

## R2. What the form sends today

- **Finding**: For a staged number pool, `buildFromPoolPayload` returns `{ id }`, so create and
  update send `{ <attr>: { from_pool: { id } } }` without a `value` key.
- **Consequence**: On create this is contract row 9 (allocate over the default). On an edit form
  over a non-default number it is row 10 or 12: the backend refuses.
- **Decision**: Always send `value` with `from_pool` for number pools (FR-007). Rows 10 and 12 are
  then unreachable from the form.

## R3. How to store the staged number

- **Options**: (a) nested field `<name>.value.from_pool.number`, like the IP prefix-length
  override; (b) a second top-level form field; (c) put the number in `value` beside `from_pool`.
- **Decision**: (a). It keeps the field's whole state in one form value, so switching tabs
  (which resets the host field to its default) discards it with no extra code, and the payload
  builders read it from the same object as the pool id.
- **Rejected**: (b) needs its own reset on tab switch and its own unchanged-detection; (c) breaks
  the `AttributeValueFromPool` shape that every pool consumer narrows on.

## R4. Edit-mode tab

- **Finding**: IFC-2764 FR-017 opens every pool-backed field on the value tab, because an IP pool
  tab cannot display a resolved allocation. `getDefaultValueFromPool` currently casts the raw
  number into the `from_pool` shape (`as unknown as`), which is wrong for a number.
- **Decision**: For a `CoreNumberPool` source, the default value is
  `{ from_pool: { id, number: <current> } }` and the field opens on the pool tab. The pool tab
  shows the pool and the number, so it is the only place that shows the whole tracked state.
- **Consequence**: The Value tab on an edit form means "a number no pool tracks", which gives
  detach (row 13) a direct gesture: switch to Value, save a number.
- **Rejected**: Value tab with a pool badge (IFC-2764 behaviour). Editing the number there would
  send `value` alone (row 5): the number changes while the pool keeps tracking it, which is
  neither "no pool" nor visibly "in the pool".

## R5. Detach gesture

- **Decision**: Saving a number from the Value tab when the default source is a number pool sends
  `{ value: n, from_pool: null }`. Visiting the Value tab without typing resets the field to its
  default, so nothing is sent (FR-012).
- **Rejected**: A separate "Remove from pool" button. Not requested; the Value tab already
  expresses it.

## R6. Refusal and backend errors

- **Decision**: No special UI. The form never sends the refused combination; any backend error
  (uniqueness, refusal, pool not attached to this kind and attribute) reaches the user through the
  existing mutation error handling of the form.

## R7. Re-selecting a pool while a pool already tracks the number and the number is emptied

- **Finding**: Row 7: the pool returns the number it already reserved for the node, so nothing
  changes.
- **Decision**: Send it anyway (it is idempotent). No special handling.

## R8. Number pre-filled when a pool is picked

- **Decision**: Pre-fill with the number staged in the pool tab, else the number the node holds
  (edit form, user or pool source). Leave it empty for a schema default, a profile or a template.
- **Rationale**: On an edit form, an empty number would allocate a new number and silently replace
  the one the node holds, which is the behaviour INFP-308 sets out to end. On a create form, a
  schema default is not a number the user chose, so allocation stays the default action.
- **Rejected**: Always empty (replaces held numbers by accident); always pre-filled including
  schema defaults (a create form would attach the default instead of allocating).

## R9. Template-backed fields

- **Finding**: `PoolAllocationPanel` already hides overrides when `fromPoolRelationshipName` is
  set, because the template relationship carries only a pool reference.
- **Decision**: `PoolNumberField` follows the same rule. Template payloads are unchanged.

## R10. Backend acceptance of the payloads the form sends

- **Finding**: `backend/infrahub/pools/intent.py::FromPoolIntentResolver` tells an explicit
  `null` apart from an absent key (`Sent`), and `attribute_pool_applier.py` builds the request
  from `value_presence` and `from_pool_presence`.
  - `{ value: null, from_pool: { id } }` resolves to `ALLOCATE` whatever pool tracks the number
    (`backend/tests/unit/pools/test_intent.py`: `null_value_with_pool_untracked_discards_and_allocates`,
    `null_value_with_tracking_pool_discards_and_allocates`, `null_value_with_other_pool_re_pools_and_allocates`).
    On a create form no pool tracks the number and no number is held, so this is backend row 6.
  - `{ value: n, from_pool: null }` resolves to `DETACH` when a pool tracks the number and to
    `NO_OP` otherwise (`null_pool_with_value_on_tracked_attribute_detaches`,
    `null_pool_with_value_on_untracked_attribute_is_no_op`); `value` is then written as an
    ordinary value write (backend row 13).
  - Row 7 (`value: null` with the pool that already tracks the number) resolves to `ALLOCATE`; the
    allocator returns the number the pool already reserved for the node, per
    [`from-pool-intent.md`](../ifc-3184-pool-number-attach/contracts/from-pool-intent.md) row 7.
- **Decision**: No gap. Every row of `contracts/form-submission.md` maps to a backend row the
  resolver handles, so the frontend work proceeds with no backend change.
