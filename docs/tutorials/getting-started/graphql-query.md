---
label: Introduction & GraphQL queries
# icon: file-directory
tags: [tutorial]
order: 450
---

# Explore the GraphQL interface

The GraphQL interface is accessible at [http://localhost:8000/graphql](http://localhost:8000/graphql)

## Introduction to GraphQL

GraphQL is the main interface to programmatically interact with Infrahub. With the GraphQL interface, it's possible to perform all the standard CRUD operations (Create, Read, Update, and Delete) on any objects in the database.

In GraphQL terminology, a `query` references any read operation and a `mutation` references any write operation that may change the value of the data. Infrahub support both `query` and `mutation` for all objects.

One of the main concepts behind GraphQL is the presence of a schema that defines what type of information we have in the database and how these objects are related to each other. Based on this schema, a user can execute queries that will return data.

Unlike a REST API, the format of the response is not fixed in GraphQL. It depends on the query, which ensures you get back only that you asked for.

## First query

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

## Filter results

Query all interfaces and IP addresses for `ord1-edge`.

```graphql # GraphQL query with a top level filter
# Endpoint : http://127.0.0.1:8000/graphql/main
query DeviceIPAddresses {
  InfraInterfaceL3(device__name__value:"ord1-edge1") {
    edges {
      node {
        name { value }
        description { value }
        ip_addresses {
          edges {
            node {
              address {
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
