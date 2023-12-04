---
label: GraphQL queries
layout: default
---
# GraphQL

The GraphQL interface is the main interface to interact with Infrahub. The GraphQL schema is automatically generated based on the core models and the user-defined schema models.

The endpoint to interact with the main branch is accessible at `https://<host>/graphql`.
To interact with a branch the URL must include the name of the branch, such as `https://<host>/graphql/<branch_name>`.

## Query & mutations

For each model in the schema, a GraphQL query and 3 mutations will be generated based on the namespace and the name of the model.

For example, for the model `CoreRepository` the following query and mutations have been generated:

- `Query` : **CoreRepository**
- `Mutation` : **CoreRepositoryCreate**
- `Mutation` : **CoreRepositoryUpdate**
- `Mutation` : **CoreRepositoryDelete**

### Query format

The top level query for each model will always return a list of objects and the query will have the following format `CoreRepository` > `edges` > `node` > `display_label`

```graphql
query {
    CoreRepository {            # PaginatedCoreRepository object
        count
        edges {                 # EdgedCoreRepository object
            node {              # CoreRepository object
                id
                display_label
                __typename
            }
        }
    }
}
```

!!!info
All list of objects will be nested under `edges` & `node` to make it possible to control the pagination and access the attribute `count`.
!!!

#### `ID` and `display_label`

For all nodes, the attribute `id` and `display_label` are automatically available. The value used to generate the `display_label` can be defined for each model in the schema. If no value has been provided a generic display label with the kind and the ID of the Node will be generated.

At the object level, there are mainly 3 types of resources that can be accessed, each with a different format:

- `Attribute`
- `Relationship` of `Cardinality One`
- `Relationship` of `Cardinality Many`

#### Attribute

Each attribute is its own object in GraphQL to expose the value and all the metadata.

In the query below, to access the attribute **name** of the object the query must be `CoreRepository` > `edges` > `node` > `name` > `value`.
At the same level all the metadata of the attribute are also available example: `is_protected`, `is_visible`, `source` & `owner`

```graphql #6-14 Example query to access the value and the properties of the attribute 'name'
query {
    CoreRepository {
        count
        edges {
            node {
                name {              # TextAttribute object
                    value
                    is_protected
                    is_visible
                    source {
                        id
                        display_label
                    }
                }
            }
        }
    }
}
```

#### Relationship of `Cardinality One`

A relationship to another model with a cardinality of `One` will be represented with a `NestedEdged` object composed of a `node` and a `properties` objects. The `node` gives access to the remote `node` (the peer of the relationship) while `properties` gives access to the properties of the relationship itself.

```graphql #6-19 Example query to access the peer and the properties of the relationship 'account', with a cardinality of one.
query {
    CoreRepository {
        count
        edges {
            node {
                account {
                    properties {
                        is_visible
                        is_propected
                        source {
                            id
                            display_label
                        }
                    }
                    node {
                        display_label
                        id
                    }
                }
            }
        }
    }
}
```

#### Relationship of `Cardinality Many`

A relationship with a cardinality of `Many` will be represented with a `NestedPaginated` object composed. It was the same format as the top level `PaginatedObject` with `count` and `edges` but the child element will expose both `node` and `properties`. The `node` gives access to the remote `node` (the peer of the relationship) while `properties` gives access to the properties of the relationship itself.

```graphql #6-20 Example query to access the relationship 'tags', with a cardinality of Many.
query {
    CoreRepository {
        count
        edges {
            node {
                tags {                      # NestedPaginatedBuiltinTag object
                    count
                    edges {                 # NestedEdgedBuiltinTag object
                        properties {
                            is_protected
                            source {
                                id
                            }
                        }
                        node {
                            display_label
                            id
                        }
                    }
                }
            }
        }
    }
}
```

### Mutations format

The format of the mutation to `Create` and `Update` an object has some similarities with the query format. The format will be slightly different for:

- An `Attribute`
- A relationship of `Cardinality One`
- A relationship of `Cardinality Many`

#### Create and update

To `Create` or `Update` an object, the mutations will have the following properties.

- The input for the mutation must be provided inside `data`.
- All mutations will return `ok` and `object` to access some information after the mutation has been executed.
- For `Update`, it is mandatory to provide an `id`.

```graphql
mutation {
  CoreRepositoryCreate(
    data: {
      name: { value: "myrepop" },           # Attribute
      location: { value: "myrepop" },       # Attribute
      account: { id: "myaccount" },         # Relationship One
      tags: [ { id: "my_id" } ]}            # Relationship Many
  ) {
    ok
    object {
      id
    }
  }
}
```

## Branch management

In addition to the queries and the mutations automatically generated based on the schema, there are some queries and mutations to interact with the branches.

- **Query**: `Branch`, Query a list of all branches
- **Mutation**: `BranchCreate`, Create a new branch
- **Mutation**: `BranchUpdate`, Update the description of a branch
- **Mutation**: `BranchDelete`, Delete an existing branch
- **Mutation**: `BranchRebase`, Rebase an existing branch with the main branch
- **Mutation**: `BranchMerge`, Merge a branch into main
- **Mutation**: `BranchValidate`, Validate if a branch has some conflicts

## GraphQLQuery

The `GraphQLQuery` model has been designed to store a GraphQL query in order to simplify its execution and to associate it with other internal objects like `Transformation`.

A `GraphQLQuery` object can be created directly from the API or it can be imported from a Git repository.

Every time a `GraphQLQuery` is created or updated, the content of the query will be analyzed to:

- Ensure the query is valid and compatible with the schema.
- Extract some information about the query itself (see below).

### Information extracted from the query

- Type of operations present in the Query [Query, Mutation, Subscription]
- Variables accepted by the query
- Depth, number of nested levels in the query
- Height, total number of fields requested in the query
- List of Infrahub models referenced in the query

### Import from a git repository

The git agent will automatically try to import all files with the extension `.gql` into a `GraphQLQuery` with the name of the file as the name of the query.
