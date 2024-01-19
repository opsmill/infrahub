---
icon: repo-forked
label: Adding/updating external repositories
---

#### Table of contents
- [Adding a repository](#add-repository)
- [Updates from external repository](#update-from-external)
- [Updates to external repository](#update-to-external)

# Summary

Infrahub supports two different types of connections to external Git repositories
 - [**CoreRepository**](/topics/repository#core-repository) fully integrates with Git version control, including branch tracking and two-way branch synchronization.
 - [**Read-only Repository**](/topics/repository#read-only-repository) links a particular branch in Infrahub to a particular ref in the Git repository. It will only read from the Git repository. It will never make any changes to the external repository.

# Adding a repository {#add-repository}

You will need to submit an access token with your request to create a repository in Infrahub. Infrahub uses your username and this token to connect to the external Git repository.

#### Personal access token {#personal-access-token}
==- Generate a GitHub fine-grained personal access token
  1. Go to settings > Developer Settings > Personal access tokens [New GitHub token](https://github.com/settings/personal-access-tokens/new)
  2. Select Fine-grained tokens
  3. Limit the scope of the token in **Repository Access** > **Only Select Repositories**
  4. Grant the token permission
      a. If you want to create a CoreRepository using this token, then you will need to give it `Read/Write` access for the **Content** of the repository
      b. If you want to create a Read-only Repository using this token, then you will only need to give it `Read` access for the **Content** of the repository.
  ![Fine-Grained Token](../media/github_fined_grain_access_token_setup.png)
==-

## Via the web interface

  1. Log in to the Infrahub UI
  2. Go to Unified Storage > Repository or Read-only Repository
  3. Click on the `+` plus sign
  4. Complete the required information
      a. `Name` is the name you want to give the repository in Infrahub
      b. `Location` is the URL of the external repository, e.g. https://github.com/opsmill/infrahub.git
      c. `Username` is your username on the external Git provider
      d. `Password` is the Fine-grained personal access token with access to the Git repository specified in `Location`
      e. `Commit` is not necessary during creation. This field will be populated with the hash of the commit that the Infrahub Repository is currently using once it has pulled the data from the external repository.
          i. **CoreRepository**: ignored during creation and will be overwritten. 
          ii. **Read-only Repository**: can be used to point at a specific commit within the given `ref`. For example, if you want to extract data from a specific commit on the `main` branch of the external repository other than the latest commit.
      f. `Default branch` (**CoreRepository** only) is the first branch to import during initialization. All other branches on the repository will be imported in a background task after this one.
      g. `Ref` (**Read-only Repository** only) is the name of the branch, tag, or commit to import.
  ![Add a Git Repository ](../media/create_repository.png)

!!!success Validate that everything is correct
In the UI, you should see your new repository. If the repository you added doesn't have the commit property populated it means that the initial sync didn't work. Verify the location and credentials.
!!!

## Via the GraphQL interface

Using the GraphQL Interface, it is possible to add a CoreRepository or Read-only Repository via a [Mutation](/topics/graphql).

!!!info
If you are using GitHub as your Git Server, you need to have a [fine-grained personal access token](#personal-access-token) to be able to access the repository.
!!!

  1. Open the [GraphQL Interface](http://localhost:8000/graphql)
  2. Add your [authentication token](/topics/auth) with the `Headers`
  3. Copy-paste the correct mutation from below and complete the information
      a. If you are creating a CoreRepository, use this mutation
      ```GraphQL
      # Endpoint : http://127.0.0.1:8000/graphql/main
      mutation {
        CoreRepositoryCreate(
          data: {
            name: { value: "<YOUR REPOSITORY NAME>" }
            location: { value: "https://<GIT SERVER>/<YOUR GIT USERNAME>/<YOUR REPOSITORY NAME>.git" }
            username: { value: "<YOUR GIT USERNAME>" }
            password: { value: "<YOUR PERSONAL ACCESS TOKEN>" }
            # default_branch: { value: "main" }                 <--- OPTIONAL
          }
        ) {
          ok
          object {
            id
          }
        }
      }
      ```
      b. If you are creating a ReadOnlyRepository, use this mutation. **Make sure that you are on the correct Infrahub branch.** Unlike a CoreRepository, a Read-only Repository will only pull files into the Infrahub branch on which it was created
      ```GraphQL
      # Endpoint : http://127.0.0.1:8000/graphql/<BRANCH>
      mutation {
        CoreReadOnlyRepositoryCreate(
          data: {
            name: { value: "<YOUR REPOSITORY NAME>" }
            location: { value: "https://<GIT SERVER>/<YOUR GIT USERNAME>/<YOUR REPOSITORY NAME>.git" }
            username: { value: "<YOUR GIT USERNAME>" }
            password: { value: "<YOUR PERSONAL ACCESS TOKEN>" }
            ref: { value: "<BRANCH/TAG/COMMIT TO TRACK>" }
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

- The repository should be visible under [Unified Storage / Repository](http://localhost:8000/objects/CoreRepository/) or [Unified Storage / Read-only Repository](http://localhost:8000/objects/CoreReadOnlyRepository/) depending on which type of repository you created. If the repository you added doesn't have the commit property populated, then it means that the initial sync didn't work. Verify the location and credentials.
!!!

# Updates from the external repository {#update-from-external}

Read-only repositories and CoreRepositories work in different ways when it comes to tracking changes on the remote repository.

## CoreRepository

The [Infrahub Git agent](/reference/git-agent) checks for changes in external repositories several times per minute. If there are no conflicts between the remote and the Infrahub branches, the Git agent will automatically pull any new changes into the appropriate Infrahub branch.

## Read-only repository

Infrahub does not automatically update Read-only Repositories with changes on the external repository. To pull in changes from the external repository you must use an update mutation to set the `ref` **and/or** `commit` of the Read-only Repository to the desired value. This mutation will tell the Infrahub Git agent to retrieve the appropriate changes in a background task.

Example update mutation

```GraphQL
# Endpoint : http://127.0.0.1:8000/graphql/main
mutation {
  CoreReadOnlyRepositoryUpdate(
    data: {
      id: "<ID OF THE REPOSITORY>"
      ref: { value: "<BRANCH/TAG/COMMIT TO TRACK>" }
      commit: { value: "<NEW COMMIT ON THE REF TO PULL>" }
    }
  ) {
    ok
    object {
      id
    }
  }
}
```

# Updates to the external repository {#update-to-external}

## CoreRepository
When a [Proposed Change](/topics/proposed-change) is merged, if the source and destination Infrahub branches are both linked to branches on the same external Git repository, then Infrahub will handle merging the branches on the external Git repository. This is the only time that Infrahub will push changes to the external repository. Other changes made within Infrahub will not be pushed to an external repository and **could potentially be overwritten** when Infrahub pulls new commits from the external repository.

## Read-only Repository
No changes to objects owned by a Read-only Repository are ever pushed to the external Git repository.
