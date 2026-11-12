# Data Model: Run a Generator for a Node from the Node's Page

No stored data changes. The feature reads existing nodes and builds a view model in the frontend. Request shapes are in [contracts/graphql-requests.md](contracts/graphql-requests.md).

## Existing entities read

| Entity | Fields used | Notes |
|---|---|---|
| `CoreGeneratorDefinition` | `id`, `display_label`, `targets` | `targets` is the target group, cardinality one, required. |
| `CoreGroup` (any group kind) | `id`, `display_label`, `members(ids: [node id]) { count }` | Count is 1 for a direct member, 0 otherwise. |
| The node's kind | `<Kind>(member_of_groups__ids: [group id]) { count }` | Number of direct members of that kind in the group. |

The node itself comes from the page: `id`, `__typename` (its concrete kind) and its label.

## View model

### `NodeGeneratorDefinition`

One entry per generator definition that targets the node. Defined in `entities/generators/domain/model/`.

| Field | Type | Source |
|---|---|---|
| `id` | string | Generator definition `id`. |
| `label` | string | Generator definition `display_label`. |
| `groupId` | string | Target group `id`. |
| `groupLabel` | string | Target group `display_label`. |
| `isMember` | boolean | `members(ids: [node id]).count > 0`. |

### Rule: `selectNodeGeneratorDefinitions`

Inputs:

- the definitions from the first request
- a map from target group id to the count of the node's kind in that group, from the second request

Output: `NodeGeneratorDefinition[]`, keeping the definitions whose group count is greater than 0, in the order the server returned them.

Validation:

- A definition without a target group is skipped. The schema requires one, but the rule must not fail on missing data.
- A group id missing from the count map counts as 0.
- Several definitions may share one target group; each gets its own entry.

### Rule: `canRunGenerators`

Inputs: `isAuthenticated`, `isDefaultBranch`, `hasEditDefaultBranch`.

Output: `isAuthenticated && (!isDefaultBranch || hasEditDefaultBranch)`. An unresolved or failed permission check counts as false.

## Item states

Each `NodeGeneratorDefinition` renders one menu item:

| State | Condition | Rendering |
|---|---|---|
| Hidden (whole section) | `canRunGenerators` is false, requests pending or failed, or no entries | No "Generators" section. |
| Disabled, not a member | `isMember` is false | Item disabled; tooltip names the target group. |
| Enabled | `isMember` is true and no start request in flight | Item selectable. |
| Starting | the start request for this item is in flight | Item disabled, no tooltip. |

Starting returns to Enabled when the request finishes, with a success or an error message. No state tracks runs already in progress (FR-009).
