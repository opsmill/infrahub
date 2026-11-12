# Contract: Behavior a User Can Observe

No GraphQL or REST schema changes. What changes is what existing queries and mutations return, and three error cases.

## Permissions (PR 1)

| Request | Before | After |
|---|---|---|
| Global permissions loaded for a request to `/graphql/<branch>` | Group memberships, roles and role-to-permission links taken from whichever branch wrote the newest edge | Taken from the default branch, combined with `-global-` |
| Object permissions loaded for a request to `/graphql/<branch>` | Request branch | Unchanged |
| Roles in the login response | Taken from any branch | Taken from the default branch |
| `BranchMerge(name: "B")` sent to `/graphql/B` by a user who joined an administrator group only on B | Allowed | Refused with the existing permission error for `merge_branch` |
| A mutation that changes an account, sent to `/graphql/B` by a user who holds `super_admin` only through a membership added on B | Allowed | Refused with the existing permission error |

## IP pool allocation (PR 3)

| Case | Before | After |
|---|---|---|
| A value deleted on the default branch after branch B was created, then allocation on B | The value is returned again | Another value is returned |
| The pool's namespace deleted on branch B, then allocation on the default branch | A value the default branch holds may be returned | Only free values are returned |
| The pool's namespace does not exist on the allocating branch X | A value from the default namespace is computed, then an unhandled `AttributeError` | `ResourceNotFoundError` (HTTP 404) with a message naming the pool, the namespace and X |
| None of the pool's resources exist on X | Prefix pool: unhandled `IndexError("No more resources available")`. Address pool: `PoolExhaustedError` | `PoolExhaustedError` (HTTP 409) with a message naming the pool and X, for both pools |
| Some resources do not exist on X | They are used | They are skipped |

Message templates (wording to confirm in review):

- `Pool '<pool display label>' cannot allocate on branch '<X>': its namespace '<namespace display label>' does not exist on this branch.`
- `Pool '<pool display label>' cannot allocate on branch '<X>': none of its resources exist on this branch.`

## Deleting a branch-agnostic node (PR 4)

| Case | Before | After |
|---|---|---|
| A required peer on another live branch is not being deleted | The delete succeeds | `ValidationError` (HTTP 422) |
| A peer would be removed through cascade on another branch only | The delete succeeds | `ValidationError` (HTTP 422) |
| A branch-aware peer removed through cascade on the request branch also exists on another live branch, and its relationship to the deleted node is required | The delete succeeds | `ValidationError` (HTTP 422), because the cascade removes the peer on the request branch only |

One error is raised per blocking link, and it names every branch where the link blocks the delete, sorted by name:

- A required peer: `Cannot delete <kind> '<id>'. It is linked to mandatory relationship <rel> on node <peer kind> '<peer id>' on branch '<branch>'`, or `on branches '<b1>', '<b2>'`. The error path is `<peer kind>.<rel>`.
- A cascade: `Cannot delete <kind> '<id>'. Deleting it would also delete <peer kind> '<peer id>' through relationship <rel> on branch '<branch>'` (or `on branches '<b1>', '<b2>'`) `, but this delete does not remove that node there`. The error path is `<kind>.<rel>`.

A GraphQL delete mutation keys the errors by path, so two blocking peers of the same kind through the same relationship are reported as one error that names the last peer. The single-branch delete already behaves this way.

## Relationship reads (PRs 5 and 6)

| Read | Before | After |
|---|---|---|
| `CoreAccountRole.groups` on the default branch after a group was deleted that had lost the role on a branch | GraphQL error (`KeyError`) | The deleted group is not returned |
| A pool's `resources` on branch B, where a prefix was deleted on B only | Not returned, because the delete writes a branch `deleted` edge on the `-global-` link | Returned, with the values of the default branch, until the prefix exists on no live branch; the delete no longer writes the branch edge |
| A pool's `resources` on any branch, where a prefix was deleted on every live branch | Not returned | Not returned, because the retirement check closed the `-global-` link |
| `node_metadata { active_on_branches }` on a peer read through a branch-agnostic relationship (PR 7) | Field does not exist | The names of the live branches on which the peer exists, sorted by name; `null` for a peer read through any other relationship |
| A branch-agnostic relationship read on any branch, where the peer was deleted on another branch | The peer is missing, or `null` when `properties` are requested | The peer is returned |
| A peer's attribute values in that read | Each attribute from whichever branch wrote the newest edge | All values from one branch: the request branch, the default branch, then the others by name |
| A cardinality-one relationship of such a peer, changed on two branches | `ValueError: At most, one relationship expected` | One related node, from the chosen branch |
| Adding a link to a peer deleted on another branch | `NodeNotFoundError` | The link is saved |
| Adding a link to a peer deleted on every live branch | `NodeNotFoundError` | Unchanged |

## Database (PRs 5 and 6)

- The migration `m083` (PR 6) runs on upgrade. It is one-way: downgrading after it runs is not supported.
- Validating an object conversion no longer counts former peers (PR 5).
- The migration logs the counts of shape 1 and shape 2 pairs converted, and of other mixed pairs left unchanged.
- Reads before and after the migration return the same results at every timestamp.
