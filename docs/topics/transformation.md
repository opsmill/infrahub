---
label: Transformation
layout: default
---

# Transformation

A `Transformation` is a generic plugin to transform a dataset into a different format to simplify it's ingestion by third-party systems.

The output of a transformation can be either in JSON format or in plain text.
>*Currently transformations must be written in Python, but in the future more languages could be supported.*

!!!success Examples

- With the `Jinja Plugin` it's possible to generate any configuration files, in plain text format.
- With the `Python Plugin` it's possible to generate the payload expected by CloudFormation to configure a resource in AWS.

!!!

## High level design

A transformation is composed of 2 main components:

- A **GraphQL query** that will define what the input data.
- A **Transformation logic** that will process the data and transform it.

![](../media/transformation.excalidraw.svg)

!!!
The transformation will automatically inherit the parameters (variables) defined by the GraphQL query. Depending on how the GraphQL query has been constructed, a transformation can be static or work for multiple objects.
!!!

==- Common parameters
{ class="compact" }
| Name            | Type                                | Default | Required |
| --------------- | ----------------------------------- | ------- | -------- |
| **name**        | `Text`                              | -       | Yes      |
| **label**       | `Text`                              | -       | No       |
| **description** | `Text`                              | -       | No       |
| **timeout**     | `Number`                            | 10      | No       |
| **rebase**      | `Boolean`                           | False   | No       |
| **query**       | `Relationship`<br> CoreGraphQLQuery | -       | Yes      |
| **repository**  | `Relationship`<br> CoreRepository   | -       | Yes      |

==-

## Available transformations

{ class="compact" }
| Namespace | Transformation      | Description                            | Language | Output Format |
| --------- | ------------------- | -------------------------------------- | -------- | ------------- |
| Core      | **RFile**           | A file rendered from a Jinja2 template | Jinja2   | Plain Text    |
| Core      | **TransformPython** | A transform function written in Python | Python   | JSON          |

### Rendered file (Jinja2 plugin)

Infrahub can natively render any Jinja templates dynamically. Internally it's referred to as `RFile` for `Rendered File`.

An RFile is a transformation plugin for Jinja2, it can generate any file in plain text format and must be composed of 1 main Jinja2 template and 1 GraphQL query.

#### Create a Jinja rendered file (RFile)

The recommended way to create an RFile is to import it from a Git Repository.

Please refer to the guide [Creating a Jinja Rendered File](/guides/jinja2-rfile) for more information.

#### Render an RFile

An RFile can be rendered with 3 different methods:

- On demand via the REST API
- As part of an [artifact](./artifact.md)
- In CLI for development and troubleshooting [infrahubctl render](/infrahubctl/infrahubctl-render)

### TransformPython (Python plugin)

A `TransformaPython` is a transformation plugin written in Python. It can generate any dataset in JSON format and must be composed of 1 main Python Class and 1 GraphQL Query.

#### Create a Python transform

A TransformPython must be written as a Python class that inherits from `InfrahubTransform` and it must implement one `transform` method. The transform method must accept a dict and return one.

Please refer to the guide [Creating a Python transform](/guides/python-transform) for more information.

#### Render a TransformPython

An TransformPython can be rendered with 2 different methods:

- On demand via the REST API
- As part of an [Artifact](./artifact.md)
- In CLI for development and troubleshooting [infrahubctl transform](/infrahubctl/infrahubctl-transform)

## Unit testing for transformation

!!!warning
Coming Soon
!!!
