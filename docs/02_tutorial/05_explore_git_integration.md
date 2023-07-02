---
label: Integration with Git
# icon: file-directory
tags: [tutorial]
order: 500
---

One of the 3 pillar Infrahub is built on is the idea of having **Unified Version Control for Data and Files** at the same time.
The data being stored in the Graph Database and the files in Git.

When integrating a Git repository with Infrahub the Git Agent will ensure that both systems will stay in sync at any time.



# Fork & Clone the repository for the demo

Create a fork of the repository https://github.com/opsmill/infrahub-demo-edge

!!!info
The goal is to have a copy of this repo under your name this way your demo won't influence others.
!!!

Once you have created a fork in Github, you'll need a Personal Access Token to authorize Infrahub to access this repository.

==- How to create a Personal Access Token in Github

  1. Go to settings > Developer Settings > Personal access tokens
  2. Select Fine-grained tokens
  3. Limit the scope of the token in **Repository Access** > **Only Select Repositories**
  4. Grant the token permission to `Read/Write` the **Content** of the repository

  ![Fine-Grained Token](../media/github_fined_grain_access_token_setup.png)
==-


!!!
If you already cloned the repo in the past, ensure there only the main branch is present in Github.
If other branches are present, it's recommanded to delete them for now.
!!!

==- How to Delete a branch in Github

  1. Select the name of the active branch in the top left corner (usually main)
  2. Select `View All Branches` at the bottom of the popup
  3. Delete all branches but the branch `main`, with the trash icon on the right of the screen

  ![View all Branches](../media/github_view_all_branches.png)

==-

## Integrate the Git Repository with Infrahub

Currently the easiest way to add a repository is to use the GraphQL interface.

!!!info
Before moving to the next step, you'll need your personal access token previously generated in Github.
!!!

[!ref Open the GraphQL Interface](http://127.0.0.1:8000/graphql/main)

```graphqls
# Endpoint : http://127.0.0.1:8000/graphql/main
mutation {
  repository_create(
    data: {
      name: { value: "infrahub-demo-edge" }
      location: { value: "https://github.com/<YOUR GITHUB USERNAME>/infrahub-demo-edge.git" }
      username: { value: "<YOUR GITHUB USERNAME>" }
      password: { value: "<YOUR PERSONAL ACCESS TOKEN>" }
    }
  ) {
    ok
    object {
      id
    }
  }
}
```

!!!success Validate that everything is correct
In the UI, new objects that have been imported from the Git Repository should now be available:
- The repository should be visible under [Objects / Repository](http://localhost:3000/objects/repository/). If the repository you added doesn't have the commit property populated it means that the initial sync didn't work. Verify the location and credentials.
- 2 Rfile under [Objects / RFile](http://localhost:3000/objects/rfile/)
- 5 GraphQL Queries under [Objects / Graphql Query](http://localhost:3000/objects/graphql_query/)
!!!

!!!secondary Troubleshooting
If you are not seeing additional objects under `Rfile` or `GraphQL Queries`, it's possible that the `Git Agent` might not be running anymore<br>
In this case the recommended approach is to run `invoke demo.start` first to ensure that everything is working.
!!!