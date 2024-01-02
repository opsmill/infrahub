---
icon: repo
label: Loading a Schema file
---
## Schema file

The recommended way to manage and load a schema is to create a schema file in YAML format. With a schema file it's possible to:

- Define new nodes
- Extend nodes, by adding attributes or relationships to the existing nodes

At a high level, the format of the schema file looks like the following:

```yaml
---
version: '1.0'
nodes:
    - <new nodes are defined here>
extensions:
  nodes:
    - <node extensions are defined here>
```

==- Example of schema file that is defining new nodes and adding  a relationship to an existing one
:::code source="../../../models/infrastructure_extension_rack.yml" :::
==-

### Load a schema file

Schema files can be loaded into Infrahub with the `infrahubctl` command or directly via the Git integration
<!-- vale off -->
#### infrahubctl command
<!-- vale on -->
The `infrahubctl` command can be used to load individual schema files or multiple files as part of a directory.

```sh
infrahubctl schema load <path to schema file or a directory> <path to schema file or a directory>
```


#### Git integration

The schemas that should be loaded must be declared in the ``.infrahub.yml`` directory, under schemas.

> Individual files and directory are both supported.

```yaml
---
schemas:
  - schemas/demo_edge_fabric.yml
```
