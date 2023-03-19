---
label: Integration with Git
# icon: file-directory
tags: [tutorial]
order: 500
---

### Fork & Clone the repository for the demo

Create a fork of the repository https://github.com/opsmill/infrahub-demo-edge
The goal is to have a copy of this repo under your name this way your demo won't influence others.

Once you have created a fork in Github, you'll need a Personal Access Token to authorize Infrahub to access this repository.

==- How to create a Personal Access Token in Github

  1. Go to settings > Developer Settings > Personal access tokens
  2. Select Fine-grained tokens
  3. Limit the scope of the token in **Repository Access** > **Only Select Repositories**
  4. Grant the token permission to `Read/Write` the **Content** of the repository

  ![Fine-Grained Token](../media/github_fined_grain_access_token_setup.png)
==-


> If you already cloned the repo in the past, ensure there only the main branch is present in Github.
If you other branches are present, it's recommanded to delete them for now.

==- How to Delete a branch in Github

  1. Select the name of the active branch in the top left corner (usually main)
  2. Select `View All Branches` at the bottom of the popup
  3. Delete all branches but the branch `main`, with the trash icon on the right of the screen

  ![View all Branches](../media/github_view_all_branches.png)

==-


## Integrate the Git Repository with the data in the Graph


```graphql
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

### Validate that all resources included in the Git repository are working properly

[!ref Full config for the device `ord1-edge1` should render properly](http://localhost:8000/rfile/device_startup?device=ord1-edge1)
[!ref The Data Transformation endpoint in the **Openconfig Interface** format should be operational](http://localhost:8000/transform/openconfig/interfaces?device=ord1-edge1)
