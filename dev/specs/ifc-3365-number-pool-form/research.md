# Research: Number pool create and edit form

Each entry records a decision, the reason for it, and what else was considered. Code is cited as `path::symbol`, with paths relative to `frontend/app/src/` unless they start with `backend/` or `tests/`.

## R1. One routing point opens the form

**Decision**: Replace `NumberPoolForm` behind `shared/components/form/object-form.tsx::ObjectForm`, which routes the `CoreNumberPool` kind. Keep the callers as they are: each one already owns the `Sheet` and its title, and passes `onSuccess` and `onCancel`.

**Rationale**: Every way of creating or editing a number pool reaches this one branch:
- the object list "Add" button (`shared/components/form/object-create-form-trigger.tsx::ObjectCreateFormTrigger`);
- the resource manager "Add" button, through `shared/components/form/generic-object-form.tsx`;
- relationship "+ Add new" (`entities/nodes/relationships/ui/add-relationship-action.tsx::AddRelationshipAction`);
- the relationship tab's "Associate a new" action;
- the Edit action on the details page (`entities/resource-manager/ui/number-pool/number-pool-actions-menu.tsx::NumberPoolActionsMenu`), through `ObjectEdit`.

**Alternatives considered**: Opening the new form only from the details page and the resource manager. Rejected, because two number pool forms would then exist side by side.

## R2. Edit mode comes from `isUpdate`, not from `currentObject`

**Decision**: The form decides between create and edit from `ObjectFormProps.isUpdate`.

**Rationale**: `AddRelationshipAction` passes `currentObject` as a prefill for a create. The current form treats any `currentObject` as an edit, so a prefilled create from a relationship input would open in edit mode.

**Alternatives considered**: None. Basing the decision on `currentObject` is the defect being avoided.

## R3. Save through the generic object mutations

**Decision**: Save with `entities/nodes/object/ui/queries/create-object.mutation.ts::useCreateObjectMutation` and `update-object.mutation.ts::useUpdateObjectMutation`. Add one optional setting on that path that turns off the client's global error toast:
- the hooks pass it to the use cases `create-object.ts::createObject` and `update-object.ts::updateObject`;
- the use cases pass it to the fetchers `create-object-from-api.ts::createObjectFromApi` and `update-object-from-api.ts::updateObjectFromApi`;
- the fetchers put it on the request `context` as `processErrorMessage`.

**Rationale**:
- **The payload is free-form:** the generic fetchers take `data: Record<string, unknown>` and serialize it with `jsonToGraphQLQuery`, so `ranges` and `allocation_scope` need no new fetcher.
- **Data refresh is already handled:**
  - Create refreshes `objectQueryKeys.all`.
  - Update refreshes `objectItemEditQueryKeys.all` and `objectQueryKeys.all`.
  - The details page's Edit caller refreshes `resourceManagerQueryKeys.all` in its own `onSuccess`.
- **The toast is the only gap:** `shared/api/graphql/error-handling.ts::handleGraphQLErrors` shows a toast for every GraphQL error unless the request `context` has `processErrorMessage` (`shared/api/graphql/types.ts::GraphQLRequestContext`). Without the new setting, the form's inline error (FR-021) would appear next to a duplicate toast.

**Alternatives considered**: New `create-number-pool-from-api` and `update-number-pool-from-api` fetchers, with their own use cases and hooks in `resource-manager`. Rejected: they would repeat the generic path to change one request option.
- Saving an edit through `ObjectEdit`'s `onSubmit` and `getUpdateMutationFromFormData`, as other forms do. Rejected:
  - `ranges` is a mutation input, not a schema field, so the generic builder would need a new field kind;
  - the stored ranges still need their own query;
  - the row strings still need converting to numbers;
  - `ObjectEdit` would need to stop its global toast.

  The pool forms build and save their own payload instead, and `ObjectForm` says so where it routes them.

## R4. Payload typing and number encoding

**Decision**: Type `BigInt` as `number` on the client, and build the save payload as the generated `CoreNumberPoolCreateInput` and `CoreNumberPoolUpdateInput`:
- **Codegen:** `graphql.config.ts` maps the `BigInt` scalar to `number`.
- **gql.tada:** `shared/api/graphql/client.ts` creates `graphql` with `initGraphQLTada<{ introspection; scalars: { BigInt: number } }>()`, so query results type `BigInt` fields as `number` instead of `unknown`. The type cache (`graphql-cache.d.ts`) must be regenerated from scratch after a scalar change, because its entries are keyed by query text.
- **Encoding:** range values are sent as JavaScript numbers.
- **Size limit:** the whole-number check also refuses values above `Number.MAX_SAFE_INTEGER`, with the message "Too large".

(Revised during implementation. The first version typed `BigInt` as `string` in codegen and `unknown` in gql.tada, which needed a payload override type and a number conversion in each mapper.)

**Rationale**:
- **The API sends numbers:** graphene serializes `BigInt` as a JSON number, and the generic fetchers write values inline into the query, where graphene's `BigInt` accepts only an integer literal. Typing it as `number` matches both directions.
- **Precision:** JavaScript numbers are exact up to 2^53 − 1. That covers the usual pool attributes, such as VLAN IDs, 32-bit AS numbers and unit IDs. The browser can't represent larger values exactly, so it can't send them.

**Alternatives considered**:
- Keeping `BigInt` as `string`/`unknown` and converting at each boundary. Rejected: every mapper repeats the conversion, and the payload needs its own type in place of the generated one.
- Sending GraphQL variables instead of inline literals, where `BigInt` accepts a string. That would mean changing how the generic fetchers build every create and update request.

## R5. Loading a pool's stored ranges for edit

**Decision**: Extend `entities/resource-manager/api/get-number-pool-from-api.ts::GET_NUMBER_POOL` to request `ranges` with `start`, `end` and `allocation_weight`. Map the result into `NumberPoolData`, with `allocation_weight` as `number | null`. The edit form reads it through the existing `useGetNumberPool` query.

**Rationale**:
- **The generic edit query skips ranges:** `GetObjectForEditForm` requests only relationships of kind `Attribute` or `Parent` (`shared/components/form/utils/getRelationshipsForForm.ts`, `view-config.ts::relationshipKindForForm`). `ranges` is a `Component` relationship (`backend/infrahub/core/schema/definitions/core/resource_pool.py`, relationship `ranges`).
- **The utilization query is the wrong source:** `InfrahubNumberPoolUtilization` reports a range with no weight as `0` (`backend/infrahub/graphql/queries/number_pool.py`, field `weight`). If the form loaded weights from it, saving would turn every stored empty weight into a stored `0`. Allocation would not change, but every save would write a weight change.
- **Refresh is already handled:** the details page's Edit caller already refreshes `resourceManagerQueryKeys.all`, which covers this query.

**Alternatives considered**:
- Reading ranges from the utilization query. Rejected because of the weight problem above.
- A separate ranges query. Rejected, because the pool query already exists and the details page refreshes its cache.

## R6. Form library

**Decision**: Build the form with react-hook-form, using `shared/components/ui/form.tsx` (`Form`, `FormField`, `FormMessage`). react-hook-form holds all of the form's state, and the form keeps none in `useState`:
- **Values:** `useForm<NumberPoolFormValues>()` in the create and edit forms, passed to the shared `Form` with its `form` prop. The shared `Form` is generic over its values, so `onSubmit` receives `NumberPoolFormData` without a cast or a guard. The range rows use `useFieldArray`.
- **Validation:** one rule per input, including the overlap check, with errors read from `formState.errors`.
- **Backend refusals:** `setError("root.server", …)` for every refusal. The shared `Form` resets with `keepErrors: true` after a submit, so these errors stay visible. Build the selects with `@infrahub/ui` (`Select`, `Autocomplete`, `ListBox`, `Popover`) and the scope chips with react-aria's `TagGroup`, as `entities/nodes/filters/ui/active-filter-tags.tsx` does.

**Rationale**: `dev/guidelines/frontend/object-forms.md` prescribes react-hook-form for forms. `dev/knowledge/frontend/shared-components.md` points to `@infrahub/ui` for selects and popovers. The prototype keeps its state in `useState` and does not carry over.

**Alternatives considered**: react-aria-components `Form`, `TextField` and `NumberField`. Rejected: the app does not use them outside the prototype, and the form guideline does not cover them.

## R7. Domain rules repeat two backend checks

**Decision**: Add three pure functions to `entities/resource-manager/domain/rules/`:
- `can-number-pool-allocate-to.ts::canNumberPoolAllocateTo(attribute)` is true for a `Number` attribute that is not read-only.
- `can-number-pool-be-scoped-by.ts::canNumberPoolBeScopedBy(field)` takes one attribute or relationship schema. It is true when the field meets the per-field conditions of `backend/infrahub/pools/scope.py::AllocationScopeValidator.check_element`:
  - for a relationship, cardinality one;
  - for an attribute, a kind other than List, JSON or Any (`NON_SCALAR_ATTRIBUTE_KINDS`);
  - the field is not optional.
- `find-overlapping-ranges.ts::findOverlappingRanges` (described below).

Each rule answers one question about a single schema field, and the form builds its lists by filtering with it:
- the node list keeps schemas where some attribute passes `canNumberPoolAllocateTo`;
- the attribute list keeps the attributes that pass it;
- the scope list keeps the fields that pass `canNumberPoolBeScopedBy`.

The backend's remaining condition, "not the allocated attribute itself", depends on the form's current choice, so the form applies it when it filters, not inside the rule.
- `find-overlapping-ranges.ts::findOverlappingRanges` returns the ranges that overlap another one, from plain start and end values.

**Rationale**: The spec asks the form to hide fields the backend refuses (FR-006) and to flag overlaps before sending (FR-011). Both repeat a backend rule. The backend still makes the final check. See Complexity Tracking in `plan.md`.

The "unique attribute" condition (`AllocationScopeValidator.validate`) stays out of `canNumberPoolBeScopedBy`. The form checks `attribute.unique` itself, because it shows a reason specific to that case (FR-007).

**Alternatives considered**: Showing every field and letting the backend refuse on save. Rejected by the user in favor of hiding unusable fields.

## R8. Scope labels in the read-only summary

**Decision**: The edit form's read-only summary finds each scope entry's field by its `name` in the node's schema and shows the field's label. If the field is missing, it shows the name. This is a lookup inside the `ui/` component, not a domain rule.

**Rationale**: The backend stores the scope as `[{id, name}]` and updates `name` when the schema renames a field (`backend/infrahub/pools/scope.py`, `refresh_names`), so the name is current. The generic edit query returns the raw stored value, so the form does not depend on the details page's mapper (`api/number-pool.mappers.ts::mapToNumberPoolData`), which reads a stored scope as empty.

**Alternatives considered**: A domain rule that matches by ID, then by name. Rejected: one caller and one lookup.

## R9. Errors from a refused save

**Decision**: When a save is rejected:
- the sheet stays open, and react-hook-form keeps every value;
- the backend's message shows in one alert above the footer, set with `setError("root.server", …)`;
- the form does not parse the message to place it under a field.

(Revised during implementation. The first version recognized the backend's " at allocation_scope" suffix and showed those messages under "Scoped by". The user asked for one message above the footer for every refusal.)

**Rationale**: The client throws `Error(messages.join("; "))` after handling GraphQL errors, so `mutateAsync` rejects with the backend's text. No form in the app shows a backend error inline today, so this form sets the pattern.

**Alternatives considered**: Keeping the global toast only. Rejected by FR-021.

## R10. Tests and documentation affected

**Decision**: Update these:
- **`tests/e2e/resource-manager/test_number_pool.py::TestNumberPool`:** new labels in the existing tests, and new tests for the P1 and P2 scenarios.
- **`tests/e2e/object-template/test_template_with_number_pool.py`:** new labels in `test_create_a_number_pool_for_module_capacity`.
- **`tests/e2e/tutorial/guides/test_resource_manager_guide.py::test_number_pool`:** new labels and the docs screenshot `guides/resources-manager/resource_manager_pool_vlan`.
- **`docs/docs/resource-manager/allocate-number.mdx`:** the "Create a number pool" step, in both its Web interface tab and its GraphQL tab.

**Rationale**:
- **Old labels:** these e2e tests select the current form's labels, "Node *", "Number Attribute *", "Start range *" and "End range *".
- **Outdated doc:** the doc describes the start and end range fields in both tabs.
- **No frontend test renders the current form**, so no frontend test breaks.

**Alternatives considered**: A new e2e file. Rejected: the e2e guide prefers extending the existing number pool spec.
