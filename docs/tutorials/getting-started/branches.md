---
label: Branches and version control
# icon: file-directory
tags: [tutorial]
order: 750
---
# Manage changes with branching and version control

In Infrahub, version control is natively integrated into the graph database which opens up some new capabilities like branching, diffing, and merging data directly in the database.

The default branch is called `main`.

## Create a new branch

To get started, let's create a new **branch** that we'll call `cr1234`.

You can create a new branch in the frontend by using the button with a plus sign in the top right corner, next to the name of the current branch, i.e., 'main'.

Branch names are fairly permissive, but must conform to [git ref format](https://git-scm.com/docs/git-check-ref-format). For example, slashes (`/`) are allowed, tildes (`~`) are not.

![](../../media/tutorial/tutorial-1-branch-and-version-control.cy.ts/tutorial_1_branch_creation.png)

### Other options available

==- Create a new branch with `infrahubctl`

Use the command below to create a new branch named `cr1234`

```sh
infrahubctl branch create cr1234
```

!!!info
Execute `invoke demo.cli-git` to start a shell session that will give you access to `infrahubctl`.
!!!

==- Create a new branch using GraphQL

Use the GraphQL mutation below to create a new branch named `cr1234`. In GraphQL a 'mutation' is used
whenever you want to change data, i.e., create, update, or delete. For reading data a 'query' is used.

```graphql
# Endpoint : http://127.0.0.1:8000/graphql/main
mutation {
  BranchCreate(data: { name: "cr1234", is_data_only: false}) {
    ok
    object {
      id
      name
    }
  }
}
```

> You'll need to provide a header to execute this operation > `{"X-INFRAHUB-KEY":"06438eb2-8019-4776-878c-0941b1f1d1ec"}`
==-

## Modify an organization via the UI

> The name of the active branch in the top right corner should now be `cr1234`

1. Select **Organization** under Object in the left menu (near the top).
2. Select the `my-first-org` organization (created in the [previous step](./creating-an-object.md)).
3. Select the `edit` button on the top right corner.
4. Update the description attribute of the organization, for example with `Changes from branch cr1234`.
5. Save your change with the button `save`.

![Access the organizations](../../media/tutorial/tutorial-1-branch-and-version-control.cy.ts/tutorial_1_organizations.png)
![Select the my-first-org organization](../../media/tutorial/tutorial-1-branch-and-version-control.cy.ts/tutorial_1_organization_details.png)
![Select the `edit` button](../../media/tutorial/tutorial-1-branch-and-version-control.cy.ts/tutorial_1_organization_edit.png)

!!!success Validate that everything is correct
Go back to the detailed page for the Organization `my-first-org` and try to switch branches with the branch selection menu at the top.

**You should be able to see the value of the label change when you change the branch.**
!!!

## View the Diff and Merge the branch cr1234 into main

Now that we have modified some data in a controlled environment, and after validating that everything is right, we can integrate these changes in the `main` branch by merging the branch `cr1234` into main.

To view changes and merge a branch you need to:

1. Navigate to the branch page in the menu on the left under the Change Control section (or [follow this link](http://localhost:8000/branches/))

![Branches list](../../media/tutorial/tutorial-1-branch-and-version-control.cy.ts/tutorial_1_branch_list.png)

2. Select the branch `cr1234` in the list of available branches.
3. Select on the Diff button and expand the changes to view the diff between `cr1234` and `main`.

![Branch diff](../../media/tutorial/tutorial-1-branch-and-version-control.cy.ts/tutorial_1_branch_diff.png)

4. Select the `Details` button to go back.
5. Select the `Merge` button.

![Branch details](../../media/tutorial/tutorial-1-branch-and-version-control.cy.ts/tutorial_1_branch_details.png)

### Other options available

==- Merge a Branch with `infrahubctl`

Use the command below to create a new branch named `cr1234`.

```sh
infrahubctl branch merge cr1234
```

!!!info
Execute `invoke demo.cli-git` to start a shell session that will give you access to `infrahubctl`
!!!

==- Merge a Branch using GraphQL

Use the GraphQL query below to merge the branch named `cr1234`.

```graphql
# Endpoint : http://127.0.0.1:8000/graphql/main
mutation {
  BranchMerge(data: { name: "cr1234" }) {
    ok
    object {
      id
      name
    }
  }
}
```

> You'll need to provide a header to execute this operation > `{"X-INFRAHUB-KEY":"06438eb2-8019-4776-878c-0941b1f1d1ec"}`
==-

!!!success Validate that everything is correct
Go back to the detailed page for the Organization `my-first-org`.

**The object should now have the value previously defined in the branch. Try switching between the 'main' branch and 'cr1234'.**
!!!
