---
label: Repository
---

#### Table of contents
- [the .infrahub.yml file](#infrahub-yaml)
    - [GraphQL Query](#graphql-query)
    - [Schema](#schema)
    - [TransformJinja2](#transform-jinja-2)
    - [Python Transformation](#transform-python)
    - [Artifact Definition](#artifact-definition)
- [Architecture](#architecture)
- [Read-only Repository vs CoreRepository](#read-only-vs-core)
- [Read-only Repository](#read-only-repository)
- [CoreRepository](#core-repository)
# Summary

Infrahub supports two different types of connections to external Git repositories
 - **CoreRepository** fully integrates with Git version control, including branch tracking and two-way branch synchronization.
 - **Read-only Repository** links a particular branch in Infrahub to a particular ref in the Git repository. It will only read from the Git repository. It will never make any changes to the external repository.

See the [guide](/guides/repository) for instructions on creating and updating repositories in Infrahub.

## `.infrahub.yml` file {#infrahub-yaml}

To make full use of a remote repository (CoreRepository or Read-only Repository) within Infrahub, the remote repository must have a `.infrahub.yml` file defined at the root of the repository. Without this file, Infrahub will only load GraphQL queries defined within the repository and it will ignore any other Infrahub data types.

An external repository can be used to link the following Infrahub objects to an Infrahub instance:

- [GraphQL Queries](/topics/graphql)
- [Schema](/topics/schema)
- [Jinja2 Transform](/topics/transformation#rendered-file-jinja2-plugin)
- [Python Transformation](/topics/transformation#transformpython-python-plugin)
- [Artifact Definition](/topics/artifact)

### GraphQL Query {#graphql-query}
This is the easiest type of object to link to Infrahub through an external repository because they do not need to be specified in the `.infrahub.yml` file. When Infrahub creates a Repository or pulls changes from the associated external repository, it will scan all the files in the repository and save any that have a `.gql` extension as GraphQLQuery objects in Infrahub.

### Schema {#schema}
Schema to be loaded as part of an external repository can be defined in file(s) as described [here](/topics/schema). The schema must also be explicitly identified in the `.infrahub.yml` file under `schemas`.

For example
```YAML
schemas:
  - schemas/demo_edge_fabric.yml
```
Infrahub will attempt to import any schema defined in `.infrahub.yml` when pulling from the external repository.

### TransformJinja2 {#transform-jinja-2}
Jinja2 Transforms can be defined as described [here](/topics/transformation#rendered-file-jinja2-plugin). To load Jinja2 Transforms into Infrahub from an external repository, you must explicitly define them in the `.infrahub.yml` file. Each Jinja2 Transform defined in the `.infrahub.yml` configuration file must include a `name` for the transform, the name of a `GraphQL query` to use with the transform, and a path to the Jinja2 `template`. An optional `description` is allowed.

For example
```YAML
rfiles:
  - name: device_startup
    description: "Template to generate startup configuration for network devices"
    query: "device_startup_info"
    template_path: "templates/device_startup_config.tpl.j2"
```

### Python Transformation {#transform-python}
Python Transformations can be defined as described [here](/topics/transformation#transformpython-python-plugin). To load Python Transformations from an external repository, you must explicitly define them in the `.infrahub.yml` configuration file. The definition in `.infrahub.yml` must include the `name` of the transformation, the `file_path` indicating where to find the Python file in the external repository, and the `class_name` telling Infrahub which specific class to use in the designated file.

For example
```YAML
python_transforms:
  - name: OCInterfaces
    class_name: OCInterfaces
    file_path: "transforms/openconfig.py"
```

### Artifact Definition {#artifact-definition}
Artifact Definitions can be created as described [here](/topics/artifact). To load Artifact Definitions from an external repository, you must explicitly define them in the `.infrahub.yml` configuration file. Each Artifact Definition in `.infrahub.yml` must include the following:
- `name`: the name of the Artifact Definition
- `artifact_name`: the name of the Artifact created by this Artifact Definition
- `parameters`: mapping of the input parameters required to render this Artifact
- `content_type`: the content-type of the created Artifact
- `targets`: the Group to target when generating the Artifact
- `transformation`: the name of the Transformation to use when generating the Artifact

For example
```YAML
artifact_definitions:
  - name: "Openconfig Interface for Arista devices"
    artifact_name: "openconfig-interfaces"
    parameters:
      device: "name__value"
    content_type: "application/json"
    targets: "arista_devices"
    transformation: "OCInterfaces
```

## Architecture {#architecture}
The [Infrahub web server](/reference/api-server) will only connect directly with external Git repositories during Infrahub Repository creation. Other than that, all interactions between Infrahub and remote Git repositories are handled by the [Git agent](/reference/git-agent). The Infrahub web server can send commands to the Git agent via our message broker and the Git agent can send data back to the Infrahub web server via GraphQL mutations.

```
┌──────────┐       RPC         ┌──────────┐
│ Infrahub │     Request       │          │
│    Web   ├──────────────────►│ Message  │
│  Server  │                   │  Broker  │
└──────────┘                   │          │
    ▲                          └────┬─────┘
    │                               │
    │                               │
    │GraphQL  ┌───────────┐         │
    │Mutations│           │◄────────┘   
    └─────────┤    Git    │         ┌──────────────┐
              │   Agent   │   HTTP  │              │
              │           │────────►│   Remote     │
              └───────────┘         │ Repositories │
                                    │              │
                                    └──────────────┘
```

Infrahub stores all of the data that it needs for every remote repository in a directory defined by the `git.repositories_directory` setting in `infrahub.toml`. When the Git agent receives an instruction to update a remote repository (several times a minute for every CoreRepository, when manually updated for a Read-only Repository), it pulls data from the remote repositories and saves it to the filesystem in the `git.repositories_directory` directory. The Git agent then parses the new data and sends the necessary GraphQL mutations to the Infrahub web server.


## Read-only Repository vs. CoreRepository {#read-only-vs-core}
Feature                 | CoreRepository                | Read-only Repository
------------------------|-------------------------------|---------------------
Branches                | Tracks all remote branches    | Data from one remote commit imported to one Infrahub branch
Updates **from** remote | Automatic via background task | Manually, by updating `ref` or `commit`
Updates **to** remote   | When merging Proposed Change  | No

### Read-only Repository {#read-only-repository}
Read-only Repositories will only pull data from an external repository into Infrahub and will never push any data to the external repository. A Read-only Repository will pull changes from a single `ref` (branch, tag, or commit) into the Infrahub branch(es) on which it exists. Read-only repositories are not automatically updated. To update a Read-only Repository, you must manually update the `commit` and/or `ref` property to a new value, then the Git agent will pull the appropriate commit and create the appropriate objects in Infrahub.

### CoreRepository {#core-repository}
When you create a CoreRepository, Infrahub will try to pull every branch defined in the external repository and create an associated Infrahub branch with the same name and matching data according to what is defined in the `.infrahub.yml` configuration file on the particular branch. Infrahub will attempt to sync updates from the external repository several times per minute in a background task that runs on the Git agent.

Editing a given GraphQL Query, Transform, Artifact Definition, or Schema within Infrahub **will not** result in those changes being pushed to the external repository. Infrahub will only push changes to an external repository when a [Proposed Change](/topics/proposed-change) is merged for which the source and destination branch are both linked to branches on the same external repository. In this case, Infrahub will attempt to create a merge commit and push that commit to the destination branch on the external repository.
