# Contract: Generators Section in the Node Actions Menu

The user-facing behavior that tests and reviewers check. The section renders inside the Actions menu (`data-testid="object-details-menu"`) of every page that uses `ObjectDetailsMenu`: node detail pages, and IP prefix and IP address pages.

## Placement

The "Generators" section comes after "Go to" and after the "Repository" section when present, and before "Manage".

## Visibility

| User | Branch | Node | Result |
|---|---|---|---|
| Not signed in | any | any | No section |
| Signed in, without `edit_default_branch` | default branch | any | No section |
| Signed in, with `edit_default_branch` (or `super_admin`) | default branch | targeted kind | Section shown |
| Signed in | any other branch | targeted kind | Section shown |
| Signed in | any | kind contained in no target group | No section |

A kind is "targeted" by a generator definition when the definition's target group contains at least one node of that kind on the branch being viewed.

## Items

One item per targeted generator definition, in the order the server returns them.

| Element | Content |
|---|---|
| Section title | `Generators` |
| Item label | `Run <generator definition label>`, with a play icon |
| Disabled item tooltip | `<node label> is not a member of the target group <group label>` |

- An item is disabled when the node is not a direct member of the target group, and while its own start request is being sent.
- The tooltip shows only for the not-a-member case.

## After selecting an item

No confirmation dialog. The run starts at once for this node only.

| Outcome | Message |
|---|---|
| Started | Success toast `Generator <generator definition label> started for <node label>.` with a `View task` link to `/tasks/<task id>`, keeping the page's `branch` query parameter |
| Refused or failed to start | Error toast `Could not start generator <generator definition label>: <server message>` |

Each outcome shows exactly one toast.

## Freshness

- The section's data is read each time the menu opens after it went stale: after adding or removing the node to or from a group, editing the node, or using the page's refresh button.
- After the node is added to the target group, reopening the menu shows the item enabled.
