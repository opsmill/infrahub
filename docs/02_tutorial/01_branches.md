---
label: Branches and Version Control
# icon: file-directory
tags: [tutorial]
order: 800
---

In Infrahub, Version Control is natively integrated into the graph database which opens up some new capabilities like : Branching, Diffing and Merging data directly in the database.

The default branch is called `main`.


## Create a new Branch

==- Create a new Branch using the Frontend


==- Create a new Branch with `infrahubctl`

Use the command line below to create a new branch named `cr1234`
```
infrahubctl branch create cr1234
```

!!!info
Execute `invoke demo.cli-git` to start a shell session that will give you access to `infrahubctl`
!!!

==- Create a new Branch using GraphQL

Use the GraphQL query below to create a new branch named `cr1234`

```graphql
# Endpoint : http://127.0.0.1:8000/graphql/main
mutation {
  branch_create(data: { name: "cr1234", is_data_only: false}) {
    ok
    object {
      id
      name
    }
  }
}
```



==-


### Modify the Admin Account via the UI


1. Reload the main page in order to refresh the list of branches
2. Navigate to [http://localhost:3000/objects/account](http://localhost:3000/objects/account)
3. Select the `admin` account (should be the only one)
4. Select the newly created branch `cr1234` in the branch menu
![Select the newly created branch `cr1234`](../media/tutorial_branch_select.png)

5. Select the `edit` button on the top right corner

![Select the `edit` button](../media/tutorial_account_edit.png)

6. Update the label attribute of the Admin account, for example with `Administrator`
7. Save your change with the button `save`


!!!success
Go back to the detailed page for the Account `Admin` and try to switch branches with the branch selection menu at the top, you should be able to see the value of the label change when you change the branch.
!!!

### Merge the branch cr1234 into Main

Now that we have modify some data in a controled environment, and after validating that everything is right, we can integrate these changes in the `main` branch by merging the branch `cr1234` into main.

==- Merge a Branch with `infrahubctl`

Use the command line below to create a new branch named `cr1234`
```
infrahubctl branch merge cr1234
```

!!!info
Execute `invoke demo.cli-git` to start a shell session that will give you access to `infrahubctl`
!!!

==- Merge a Branch using GraphQL

Use the GraphQL query below to create a new branch named `cr1234`

```graphql
# Endpoint : http://127.0.0.1:8000/graphql/main
mutation {
  branch_merge(data: { name: "cr1234" }) {
    ok
    object {
      id
      name
    }
  }
}
```


==- Merge a Branch using the Frontend
!!!warning
It's not yet possible to merge a branch via the frontend
!!!
==-

!!!success
Go back to the detailed page for the Account `Admin`, the object should now have the value previously defined in the branch.
!!!



