# Schema

In Infrahub, the schema is at the center of most things and our goal is to provide as much flexibility as possible to the users to extend and customize the schema.

Out of the box, Infrahub doesn't have a schema for most things and it's up to the users to load a schema that fits their needs. Over time we are planning to maintain different schemas for the common type of use cases, but for now, we are providing one example schema to model a simple network with basic objects like Device, Interface, IPAddress etc

Unlike traditional databases that can only have one schema at a time, in Infrahub, it will be possible to have a different schema per branch(*). This is possible because the schema itself is stored in the database like any other object.

New schema can be uploaded via the REST API and individual parts of the schema can be modified via the GraphQL Interface or the Frontend.

_(*) Not available yet_


!!!info
In the Tech Preview not all features of the schema are available yet, there are still some important changes coming like the support for: branches, namespaces and schema dependencies.
!!!

## Node, Attributes, Relationships & Generics

The schema is composed of 4 primary type of object : [!badge Nodes] that are themselves composed of [!badge Attributes] and [!badge Relationships] and finally [!badge Generics]
- A [!badge Node] in Infrahub represents a `Model`.
- An [!badge Attribute] represents a direct value associated with a [!badge Node] like a `Text`, a `Number` etc ...
- A [!badge Relationship] represents a unidirectional link between 2 [!badge Node], a [!badge Relationship] can be of cardinality `one` or `many`.
- A [!badge Generics] can be used to share some attributes between multiple [!badge Node], if you're familiar with programming concept, it's close to class inheritance.

In the example below, the node `Person` has 2 attributes (`name` and `description`) and the node `Car` has 1 attribute (`model`) and 1 relationship to `Person`, identified by 'owner'.

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
        peer: Person
        optional: false
        cardinality: one
        kind: Attribute
```

[!badge Node], [!badge Attribute] and [!badge Relationship] are defined by their `kind`. While the Kind of the node is up to the creator of the schema, the kinds for the attributes and the relationships are coming from Infrahub. The `kind` of an attribute, or a relationship, is very important because it defined how each element will be represented in GraphQL and in the UI.

### Attribute Kinds

- `Text` : Standard Text
- `Number` : Standard Number
- `TextArea` : Long form Text that can span multiple lines
- `Boolean` : Flag that can be either True or False
- `DateTime` : A Data and a Time
- `Email` : Email address
- `Password` : A Text String that should be offuscated.
- `URL` : An URL to a website or a resources over http
- `File` : Path to a file on the filesystem
- `MacAddress` : Mac Address following the format (XX:XX:XX:XX:XX:XX)
- `Color` : A html color
- `Bandwidth` : Bandwidth in kbps
- `IPHost` : Ip Address in either IPV4 or IPv6 format
- `IPNetwork` : Ip Network in either IPV4 or IPv6 format
- `Checkbox` : Duplicate of `Boolean`
- `List` : List of any value
- `Any` : Can be anything

### Relationship Kinds

- `Generic` : Default relationship without specific significance
- `Attribute` : Relationship of type Attribute are represented in the detailed view and in the list view
- `Component` : Indicate a relationship with another node that is a component of the current node, Example: Interface is a component to a Device
- `Parent` : Indicate a relationship with another node that is a parent to the current node, Example: Device is a parent to an Interface

==- Attribute Kinds Behavior in the UI
| Kind         | Display in  List View | Display in  Detailed View | { class="compact" }
|--------------|-----------------------|---------------------------|
| `ID`         | No                    | Yes                       |
| `Text`       | Yes                   | Yes                       |
| `Number`     | Yes                   | Yes                       |
| `TextArea`   | No                    | Yes                       |
| `DateTime`   | No                    | Yes                       |
| `Email`      | Yes                   | Yes                       |
| `Password`   | No                    | Yes                       |
| `URL`        | Yes                   | Yes                       |
| `File`       | Yes                   | Yes                       |
| `MacAddress` | Yes                   | Yes                       |
| `Color`      | Yes                   | Yes                       |
| `Bandwidth`  | Yes                   | Yes                       |
| `IPHost`     | Yes                   | Yes                       |
| `IPNetwork`  | Yes                   | Yes                       |
| `Checkbox`   | No                    | Yes                       |
| `List`       | No                    | Yes                       |
| `Any`        | No                    | Yes                       |

==- Relationship Kinds Behavior in the UI

| ID        | cardinality | Display in  List View | Display in  Detailed View | Display in Tab | { class="compact" }
|-----------|-------------|-----------------------|---------------------------|----------------|
|  `Generic`  |     `one`     |           No          |            Yes            |       No       |
|  `Generic` |     `many`    |           No          |             No            |       Yes      |
| `Attribute` |     `one`     |          Yes          |            Yes            |       No       |
| `Attribute` |     `many`    |          Yes          |            Yes            |       No       |
| `Component` |     `one`     |           No          |            Yes            |       No       |
| `Component` |     `many`    |           No          |             No            |       Yes      |
|   `Parent`  |     `one`     |           No          |            Yes            |       No       |
| `Parent`    |     `many`    |           No          |            Yes            |       No       |

===

## Generics

A Generic can be used to:
- Share multiple attributes or relationships between different types of nodes.
- Connect multiple types of Node to the same relationship.
- Define Attribute and Relationship on a specific list of nodes and avoid creating attributes for everything

In the example below, we took the schema that we used previously and we refactored it using Generic
Now `Car` is a Generic with 2 attributes and 1 relationship and 2 models `ElectricCar` and `GazCar` are referencing it.
In the GraphQL schema `ElectricCar` and `GazCar` will have all the attributes and the relationships of `Car` in addition to the one defined under their respective section.

```yaml
generics:
  - name: car
    kind: Car
    attributes:
      - kind: Text
        name: name
        unique: true
      - name: color
        kind: Colo
    relationships:
      - cardinality: one
        identifier: person__car
        name: owner
        optional: false
        peer: Person
nodes:
  - name: electric_car
    kind: ElectricCar
    attributes:
      - kind: Number
        name: nbr_engine
    inherit_from: [ Car ]
  - name: gaz_car
    kind: GazCar
    attributes:
      - kind: Number
        name: mpg
    inherit_from: [ Car ]
  - name: person
    kind: Person
    attributes:
      - kind: Text
        name: name
        unique: true
      - kind: Number
        name: height
        optional: true
    relationships:
      - cardinality: many
        identifier: person__car
        name: cars
        peer: Car

```
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