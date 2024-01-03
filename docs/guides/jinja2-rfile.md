---
icon: file-code
label: Creating a Jinja Rendered File (RFile)
---
# Creating a Jinja Rendered File (RFile)

Within Infrahub a [Transform](/topics/transformation) is defined in an [external repository](/topics/repository). However, during development and troubleshooting it is easiest to start from your local computer and run the render using [infrahubctl render](/infrahubctl/infrahubctl-render).

The goal of this guide is to develop a Jinja Rfile and add it to Infrahub, we will achieve this by following these steps.

1. Identify the relevant data you want to extract from the database using a [GraphQL query](/topics/graphql), that can take an input parameter to filter the data
2. Write a Jinja2 file that use the GraphQL query to read information from the system and render the data into a new format
3. Create an entry for the Rfile within an .infrahub.yml file.
4. Create a Git repository
5. Test the Rfile rendering with infrahubctl
6. Add the repository to Infrahub as an external repository
7. Validate that the Rfile works by using the render API endpoint

In this guide we are going to work with the builtin tag objects in Infrahub. It won't provide a Rfile that is very useful, the goal is instead to show how the Jinja Rendering works. Once you have mastered the basics you will be ready to go on to create more advanced template.

## 1. Creating a query to collect the desired data

As the first step we need to have some data in the database to actually query.

Create three tags, called "red", "green", "blue", either using the frontend or by submitting three GraphQL mutations as per below (just swapping out the name of the color each time).

```GraphQL
mutation CreateTags {
  BuiltinTagCreate(
    data: {name: {value: "red"}, description: {value: "The red tag"}}
  ) {
    ok
    object {
      id
    }
  }
}
```

The next step is to create a query that returns the data we just created. The rest of this guide assumes that the following query will return a response similar to the response below the query.

```GraphQL
query TagsQuery {
  BuiltinTag {
    edges {
      node {
        name {
          value
        }
        description {
          value
        }
      }
    }
  }
}
```

Response to the tags query:

```json
{
  "data": {
    "BuiltinTag": {
      "edges": [
        {
          "node": {
            "name": {
              "value": "blue"
            },
            "description": {
              "value": "The blue tag"
            }
          }
        },
        {
          "node": {
            "name": {
              "value": "green"
            },
            "description": {
              "value": "The green tag"
            }
          }
        },
        {
          "node": {
            "name": {
              "value": "red"
            },
            "description": {
              "value": "The red tag"
            }
          }
        }
      ]
    }
  }
}
```

While it would be possible to create a transform that targets all of these tags, for example if you want to create a report, the goal for us is to be able to focus on one of these objects. For this reason we need to modify the query from above to take an input parameter so that we can filter the result to what we want.

Create a local directory on your computer.

```sh
mkdir tags_render
```

Then save the below query as a text file named tags_query.gql.

```GraphQL
query TagsQuery($tag: String!) {
  BuiltinTag(name__value: $tag) {
    edges {
      node {
        name {
          value
        }
        description {
          value
        }
      }
    }
  }
}
```

Here the query will require an input parameter called `$name` what will refer to the name of each tag. When we want to query for the red tag the input variables to the query would look like this:


```json
{
  "tag": "red"
}
```

## 2. Create the Jina Template

The next step is to create the actual Jinja Template file. Create a file called tags_tpl.j2

```jinja2
{% if data.BuiltinTag.edges and data.BuiltinTag.edges is iterable %}
{% for tag in ["BuiltinTag"]["edges"][0]["node"] %}
{% set tag_name = tag.name.value %}
{% set tag_description = tag.description.value %}
{{ tag_name }}
description: {{ tag_description }}
{% endfor %}
{% endif %}
```

## 3. Create a .infrahub.yml file

In the .infrahub.yml file you define what transforms you have in your repository that you want to make available for Infrahub.

Create a .infrahub.yml file in the root of the directory.

```yaml
---
rfiles:
  - name: my-rfile                   # Unique name for your rfile
    description: "short description" # (optional)
    query: "tags_query"            # Name or ID of the GraphQLQuery
    template_path: "tags_tpl.j2" # path to the main Jinja2 template
```

> The main Jinja2 template can import other templates

Three parts here are required, first the `name` of the Rfile which should be unique across Infrahub, `query` the GraphqlQuery linked to our Rfile and also the `template_path` that should point to the Jinja2 file within the repository.

## 4. Create a Git repository

Within the `tags_render` folder you should now have tree files:

* tags_query.gql: Contains the GraphQL query
* tags_tpl.j2: Contains the Jinja2 Template
* .infrahub.yml: Contains the definition for the Rfile

Before we can test our transform we must add the files to a local Git repository.

```sh
git init --initial-branch=main
git add .
git commit -m "First commit"
```

## 5. Test the render using infrahubctl

Using infrahubctl you can first verify that the `.infrahub.yml` file is formatted correctly by listing available Rfile.

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

## 6. Adding the repository to Infrahub

In order to avoid having the same instructions over and over please refer to the guide [adding a repository to Infrahub](/guides/repository) in order to sync the repository you created and make it available within Infrahub.

## 7. Accessing the RFile from the API

An RFile can be rendered on demand via the REST API with the endpoint: `https://<host>/api/rfile/<rfile name or ID>`

This endpoint is branch-aware and it accepts the name of the branch and/or the time as URL parameters.

- `https://<host>/api/rfile/<rfile name or ID>?branch=main`
- `https://<host>/api/rfile/<rfile name or ID>?branch=main&at=<time of your choice>`

!!!info
The name of the branch used in the query will be used to retrieve the right Jinja template and to execute the GraphQL query.
!!!

If the GraphQL query accepts parameters, they can be passed directly as URL parameters:

```txt
https://<host>/api/rfile/<rfile name or ID>?branch=main&my-param=XXXXX&my-other-param=YYYYY
```
