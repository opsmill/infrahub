---
label: .infrahub.yml file format
---

# `.infrahub.yml` file {#infrahub-yaml}

To make full use of a [remote repository](/topics/repository) within Infrahub, the remote repository must have a `.infrahub.yml` file defined at the root of the repository. Without this file, Infrahub will only load GraphQL queries (`.gql` extension) defined within the repository and it will ignore any other Infrahub data types.

An external repository can be used to link the following Infrahub objects to an Infrahub instance:

- [GraphQL Query](/topics/graphql)
- [Schema](/topics/schema)
- [Jinja2 Transform](/topics/transformation#rendered-file-jinja2-plugin)
- [Python Transformation](/topics/transformation#transformpython-python-plugin)
- [Artifact Definition](/topics/artifact)

!!!info

- See [this guide](/guides/repository) for how to add or update an external repository in Infrahub
- See [this topic](/topics/repository) for more information on remote repositories in Infrahub

!!!

## GraphQL Query {#graphql-query}

This is the easiest type of object to link to Infrahub through an external repository because they do not need to be specified in the `.infrahub.yml` file. When Infrahub creates a Repository or pulls changes from the associated external repository, it will scan all the files in the repository and save any that have a `.gql` extension as GraphQLQuery objects in Infrahub.

## Schema {#schema}

Schemas to be loaded as part of an external repository can be defined in file(s) as described [here](/topics/schema). The schemas must also be explicitly identified in the `.infrahub.yml` file under `schemas`.

==- Example

```YAML
schemas:
  - schemas/demo_edge_fabric.yml
```

==-

Infrahub will attempt to import any schemas defined in `.infrahub.yml` when pulling from the external repository.

## Jinja2 Transformation {#transform-jinja-2}

Jinja2 Transformations can be defined as described [here](/topics/transformation#rendered-file-jinja2-plugin). To load Jinja2 Transformations into Infrahub from an external repository, you must explicitly define them in the `.infrahub.yml` file. Each Jinja2 Transformations in the `.infrahub.yml` configuration file is defined by the following

- `name`: name of the transform
- `query`: the name of an Infrahub `GraphQL query` to use with the transform
- `template_path`: the path to the Jinja2 template within this repository
- `description`: (**optional**) a description of the transform

==- Example

```YAML
jinja2_transforms:
  - name: device_startup
    description: "Template to generate startup configuration for network devices"
    query: "device_startup_info"
    template_path: "templates/device_startup_config.tpl.j2"
```

==-

## Python Transformation {#transform-python}

Python Transformations can be defined as described [here](/topics/transformation#transformpython-python-plugin). To load Python Transformations from an external repository, you must explicitly define them in the `.infrahub.yml` configuration file. The definition in `.infrahub.yml` includes the following

- `name`: name of the transformation
- `file_path`: path to the Python transformation within this repository
- `class_name`: which specific class to use in the Python file designated by `file_path`

==- Example

```YAML
python_transforms:
  - name: OCInterfaces
    class_name: OCInterfaces
    file_path: "transforms/openconfig.py"
```

==-

## Artifact Definition {#artifact-definition}

Artifact Definitions can be created as described [here](/topics/artifact). To load Artifact Definitions from an external repository, you must explicitly define them in the `.infrahub.yml` configuration file. Each Artifact Definition in `.infrahub.yml` must include the following:

- `name`: the name of the Artifact Definition
- `artifact_name`: the name of the Artifact created by this Artifact Definition
- `parameters`: mapping of the input parameters required to render this Artifact
- `content_type`: the content-type of the created Artifact
- `targets`: the Infrahub `Group` to target when generating the Artifact
- `transformation`: the name of the Transformation to use when generating the Artifact

==- Example

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

==-
