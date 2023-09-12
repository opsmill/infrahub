---
label: Introduction & GraphQL Query
# icon: file-directory
tags: [tutorial]
order: 200
---
## Explore the GraphQL Interface

The GraphQL interface is accessible at [http://localhost:8000/graphql](http://localhost:8000/graphql)

### Introduction to GraphQL

GraphQL is the main interface to programatically interact with Infrahub. Via the GraphQL interface, it's possible to perform all the standard CRUD operations: Create, Read, Update and Delete any objects in the database.

In GraphQL terminology, a `query` reference any read operation and a `mutation` reference any write operation that may change the value of the data.
Infrahub support both `query` and `mutation` for all objects.

One of the main concepts behind GraphQL is the presence of a Schema that defines what type of information we have in the database and how these objects are related to each other, based on this schema, a user can execute queries that will return data.

Unlike a REST API, the format of the response is not fixed in GraphQL, it depends on the query and you get back only that you asked for.


### First Query

The following query will return the name of the all the devices in the database.

```graphql # First Query
# Endpoint : http://localhost:8000/graphql/main
query {
  InfraDevice {
    edges {
      node {
        name {
          value
        }
      }
    }
  }
}
```

### Filter results

Query all interfaces and IP addresses for `ord1-edge`

```graphql # GraphQL query with a top level filter
# Endpoint : http://127.0.0.1:8000/graphql/main
query {
  InfraDevice(name__value: "ord1-edge1") {
    edges {
      node {
        name {
          value
        }
        interfaces {
          edges {
            node {
              id
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
    }
  }
}
```
