---
label: Repository
---

# Summary

Infrahub supports two different types of connections to external Git repositories

- **CoreRepository** fully integrates with Git version control, including branch tracking and two-way branch synchronization.
- **Read-only Repository** links a particular branch in Infrahub to a particular ref in the Git repository. It will only read from the Git repository. It will never make any changes to the external repository.

See the [guide](/guides/repository) for instructions on creating and updating repositories in Infrahub.

## `.infrahub.yml` file {#infrahub-yaml}

The `.infrahub.yml` configuration file specifies exactly what should be imported into Infrahub from the external repository. All GraphQL queries (`.gql` extension) within the repository will be imported automatically, but the `.infrahub.yml` file is required if you wish to import anything else, such as schemas, transformations, or artifact definitions.

See [this topic](/topics/infrahub-yml) for a full explanation of everything that can be defined in the `.infrahub.yml` file.

## Architecture {#architecture}

The [Infrahub web server](/reference/api-server) will never connect directly with external Git repositories. All interactions between Infrahub and remote Git repositories are handled by the [Git agent](/reference/git-agent). The Git agent(s) can work with any remote Git server that using either `git` or `http` protocols. The Infrahub web server can send commands to the Git agent via our message broker and the Git agent can send data back to the Infrahub web server via GraphQL mutations.

![](../media/repository_architecture.png)

Infrahub stores all of the data that it needs for every remote repository in a directory defined by the `git.repositories_directory` setting in `infrahub.toml`. When the Git agent receives an instruction to update a remote repository, it pulls data from the remote repositories and saves it to the filesystem in the `git.repositories_directory` directory. The Git agent then parses the new data and sends the necessary GraphQL mutations to the Infrahub web server. Infrahub attempts to update each CoreRepository with any changes in the remote repository several times per minute. Read-only repositories are only updated when specifically requested.

Please note that each Git agent must have access to the same directory on the file system so that they can share work among each other.

## Read-only Repository vs. CoreRepository {#read-only-vs-core}

Feature                 | CoreRepository                | Read-only Repository
------------------------|-------------------------------|---------------------
Branches                | Tracks all remote branches    | Data from one remote commit imported to one Infrahub branch
Updates **from** remote | Automatic via background task | Manually, by updating `ref` or `commit`
Updates **to** remote   | When merging Proposed Change  | No

### Read-only Repository {#read-only-repository}

Read-only Repositories will only pull data from an external repository into Infrahub and will never push any data to the external repository. A Read-only Repository will pull changes from a single `ref` (branch, tag, or commit) into the Infrahub branch(es) on which it exists. Read-only repositories are not automatically updated. To update a Read-only Repository, you must manually update the `commit` and/or `ref` property to a new value, then the Git agent will pull the appropriate commit and create the appropriate objects in Infrahub.

### CoreRepository {#core-repository}

When you create a CoreRepository, Infrahub will try to pull every branch defined in the external repository and create an associated Infrahub branch with the same name and matching data according to what is defined in the `.infrahub.yml` configuration file on the particular remote branch. Infrahub will attempt to sync updates from the external repository several times per minute in a background task that runs on the Git agent(s).

Editing a given GraphQL Query, Transform, Artifact Definition, or Schema within Infrahub **will not** result in those changes being pushed to the external repository. Infrahub will only push changes to an external repository when a [Proposed Change](/topics/proposed-change) is merged for which the source and destination branch are both linked to branches on the same external repository. In this case, Infrahub will attempt to create a merge commit and push that commit to the destination branch on the external repository.
