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

### RFile (Jinja2 plugin)

An RFile is a transformation plugin for Jinja2, it can generate any file in plain text format and must be composed of 1 main Jinja2 template and 1 GraphQL query.

#### Create an RFile

The recommended way to create an RFile is to import it from a Git Repository.

- The main Jinja2 template can be in any directory in the repository
- The GraphQL Query can be imported as well from the Git Repository or can be already existing in the database.

For Infrahub to automatically import an RFile from a Repository, it must be declare in the `.infrahub.yml` file at the root of the repository under the key `rfiles`.

```yaml
---
rfiles:
  - name: my-rfile                   # Unique name for your rfile
    description: "short description" # (optional)
    query: "my-gql-query"            # Name or ID of the GraphQLQuery
    template_path: "templates/config.tpl.j2" # path to the main Jinja2 template
```

> The main Jinja2 template can import other templates

#### Render an RFile

An RFile can be rendered with 3 different methods:

- On demand via the REST API
- As part of an [artifact](./artifact.md)
- In CLI for development and troubleshooting

##### From the REST API

An RFile can be rendered on demand via the REST API with the endpoint: `https://<host>/api/rfile/<rfile name or ID>`

This endpoint is branch-aware and it accepts the name of the branch and/or the time as URL parameters.

- `https://<host>/api/rfile/<rfile name or ID>?branch=branch33`
- `https://<host>/api/rfile/<rfile name or ID>?branch=branch33&at=<time of your choice>`

!!!info
The name of the branch used in the query will be used to retrieve the right Jinja template and to execute the GraphQL query.
!!!

If the GraphQL query accepts parameters, they can be passed directly as URL parameters:

```txt
https://<host>/api/rfile/<rfile name or ID>?branch=branch33&my-param=XXXXX&my-other-param=YYYYY
```

##### From the CLI for development and troubleshooting

The CLI command `infrahubctl` is able to find your local RFile(s) and render them for development and troubleshooting purposes.

```sh
 Usage: infrahubctl render [OPTIONS] RFILE [VARIABLES]...

 Render a local Jinja Template (RFile) for debugging purpose.

╭─ Arguments ───────────────────────────────────────────────────────────────────────────────────────╮
│ *    rfile          TEXT            [default: None] [required]                                    │
│      variables      [VARIABLES]...  Variables to pass along with the query. Format key=value      │
│                                     key=value.                                                    │
│                                     [default: None]                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────╮
│ --branch                       TEXT  Branch on which to render the RFile. [default: None]         │
│ --debug          --no-debug          [default: no-debug]                                          │
│ --config-file                  TEXT  [env var: INFRAHUBCTL_CONFIG] [default: infrahubctl.toml]    │
│ --help                               Show this message and exit.                                  │
╰───────────────────────────────────────────────────────────────────────────────────────────────────╯
```

Examples

```sh
infrahubctl render <rfile name or ID> my-param=XXXXX my-other-param=YYYYY
```

!!!info
If `--branch` is not provided it will automatically use the name of the local branch.
!!!

### TransformPython (Python plugin)

A `TransformaPython` is a transformation plugin written in Python. It can generate any dataset in JSON format and must be composed of 1 main Python Class and 1 GraphQL Query.

#### Create a TransformPython

A TransformPython must be written as a Python class that inherits from `InfrahubTransform` and it must implement one `transform` method. The transform method must accept a dict and return one.

Each TransformPython must also define the following class-level variables:

- `query`: The ID or the name of the query to use.
- `url`: The URL where this TransformPython will be exposed via the REST API.

```python
from infrahub_sdk.transforms import InfrahubTransform

class MyPythonTransformation(InfrahubTransform):

    query = "my-gql-query"
    url = "my/custom/url"

    async def transform(self, data: dict) -> dict:
        # Do something with data
        return data
```

The Git agent will automatically locate and import all `PythonTransform` in a Git repository.

#### Render a TransformPython

An TransformPython can be rendered with 2 different methods:

- On demand via the REST API
- As part of an [Artifact](./artifact.md)

##### From the REST API

A TransformPython can be rendered on demand via the REST API with the endpoint: `https://<host>/api/transform/<url defined by the TransformPython>`

This endpoint is branch-aware and it accepts the name of the branch and/or the time as URL parameters.

- `https://<host>/api/transform/my/custom/url?branch=branch33`
- `https://<host>/api/transform/my/custom/url?branch=branch33&at=<time of your choice>`

!!!info
The name of the branch used in the query will be used to retrieve the right Jinja Template and to execute the GraphQL Query
!!!

If the GraphQL query accept some parameters, they can be passed directly as URL parameters

```txt
https://<host>/api/transform/my/custom/url?branch=branch33&my-param=XXXXX&my-other-param=YYYYY
```

## Unit testing for transformation

!!!warning
Coming Soon
!!!
