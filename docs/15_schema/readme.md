# Schema

In Infrahub, the schema is at the center of most things and the goal is to provide as much flexibility as possible to the users to extend and customize the schema. Out of the box, Infrahub doesn't have a schema for most things and it's up to the user to load a schema that fits his/her needs. Over time we are planning to maintain some schemas for the common type of models that our users are using, but for now, we are providing one example of schema to model a simple network with some basic objects like Device, Interface, IPAddress etc ...

Unlike traditional databases that can only have 1 schema at a time, in Infrahub, the schema is stored in the database like any other object and as such it will be possible to have a different schema per branch(*).

New schema can be uploaded via the REST API and individual parts of the schema can be modified via the GraphQL Interface and/or the Frontend. 

_(*) Not available yet_


!!!info
In the Tech Preview not all features of the schema are available yet, there are still some important changes coming like the support branches, namespace generic objects or schema dependencies.
!!!

## Node, Attributes and Relationships

The schema is composed primarily of `nodes` that are themselves composed of `Attributes` and `Relationships`. 
- A `Node` in Infrahub represents a `Model`.
- An `Attribute` represents a direct value associated with a `Node`
- A `Relationship` represents a link to another object.

In the example below, the node `Person` has 2 attributes (`name` and `description`) and the node `Car` has 1 attribute (`model`) and 1 relationship to `Car`
```yaml
nodes:
  - name: person
    kind: Person
    attributes:
      - name: name
        kind: Text
        unique: true
      - name: description
        kind: Text
        optional: true
  - name: car
    kind: Car
    attributes:
      - name: model
        kind: Text
    relationships:
      - name: owner
        peer: Car
        optional: false
        cardinality: one
        kind: Attribute
```

`Node`, `Attribute` and `Relationship` are defined by their `kind`. While the Kind of the node is up to the creator of the schema, the kinds for the attributes and the relationships are coming from Infrahub. The `kind` of an attribute, or a relationship, is very important because it defined how each element will be represented in GraphQL and in the UI.

=== Attribute Kind

| Kind       | Description                                 | Has Filter | Behave like | Display in List View |
|------------|---------------------------------------------|------------|-------------|-----------------------|
| `ID`         |                                             | Yes        |             | Yes                   |
| `Text`       | Standard Text, replace String               | Yes        | String      | Yes                   |
| `Number`     | Standard Number, replace Integer            | Yes        | Integer     | Yes                   |
| `TextArea`   | Long form Text that can span multiple lines | No         | String      | No                    |
| `DateTime`   |                                             | Yes        | String      | Yes                   |
| `Email`      | Email address                               | Yes        | String      | Yes                   |
| `Password`   |                                             | No         | String      | No                    |
| `URL`        |                                             | Yes        | String      | Yes                   |
| `File`       |                                             | Yes        | String      | Yes                   |
| `MacAddress` |                                             | Yes        | String      | Yes                   |
| `Color`      |                                             | Yes        | String      | Yes                   |
| `Bandwidth`  |                                             | Yes        | Integer     | Yes                   |
| `IPHost`     |                                             | Yes        | String      | Yes                   |
| `IPNetwork`  |                                             | Yes        | String      | Yes                   |
| `Checkbox`   |                                             | Yes        | Boolean     | Yes                   |
| `List`       |                                             | No         | --          | Yes                   |
| `Any`        |                                             | No         | --          | No                    |
| `String`     |                                             | Yes        | --          | Yes                   |
| `Integer`    |                                             | Yes        | --          | Yes                   |
| `Boolean`    |                                             | Yes        | --          | Yes                   |

=== Relationship Kind

| Kind       | Description                                 |
|------------|---------------------------------------------|
| `Generic`    | Default relationship without specific significance  |
| `Attribute`  | Relationship of type Attribute are represented in the detailed view and in the list view  
| `Component`  | Indicate a relationship with another node that is a component of the current node, Example: Interface is a component to a Device  |
| `Parent`     | Indicate a relationship with another node that is a parent to the current node, Example: Device is a parent to an Interface   |

===

## Schema File

The recommended way to manage and load a schema is to create a schema file in Yaml format, with a schema file it's possible to
- Define new nodes
- Extend nodes, by adding attributes or relationships to the existing nodes

At a high level the format of the schema file looks like that.
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
:::code source="../../models/infrastructure_extension_rack.yml" :::
==-

### Load a Schema file

A schema file can be loaded into Infrahub with the `infrahubctl` command
```
infrahubctl schema load <path to schema file>
```

!!!warning
Currently it's mandatory to reload the `API Server` after all modifications of the schema.<br>
Simply stop and restart the `gunicorn` process to see the latest changes in the schema
!!!