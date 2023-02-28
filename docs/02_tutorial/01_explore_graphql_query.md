---
label: Introduction & GraphQL Query
# icon: file-directory
tags: [tutorial]
order: 1000
---
## Explore the GraphQL Interface

The GraphQL interface is accessible at [http://localhost:8000/graphql](http://localhost:8000/graphql)

### Introduction to GraphQL
GraphQL is the main interface to programatically interact with Infrahub. Via the GraphQL interface, it's possible to all the standard CRUD operation: 
Create, Read, Update and Device any objects in the database.

In GraphQL terminology, a `query` reference any read operation and a `mutation` reference any write operation that may change the value of the data.
Infrahub support both `query` and `mutation` for all objects.

One of the main concept behind GraphQL is the presence of a Schema that defines what can type of information we have in the database and how these objects are related to each other, based on this schema, a user can write come query that will return some data.

Unlike a REST API, the format of the payload is not fixed in GraphQL, it depends on the query and you get back only that you asked for.

TODO add more resources to learn GraphQL

### First Query

The following query will return the name of the all the devices in the database.


```graphql # Your title here
# Endpoint : http://localhost:8000/graphql/main
query {
  device {
    name {
      value
    }
  }
}
```

!!!
This is an Alert
!!!

> 

### Filter results

Query all interfaces and IP addresses for `ord1-edge`
```graphql
# Endpoint : http://127.0.0.1:8000/graphql/main
query {
  device(name__value: "ord1-edge1") {
    name {
      value
    }
    interfaces {
      id
      name {
        value
      }
      description {
        value
      }
      role {
        name {
        	value
        }
      }
    }
  }
}
```


Query all interfaces and IP addresses for `ord1-edge`
```graphql
# Endpoint : http://127.0.0.1:8000/graphql/main
query {
  device(name__value: "ord1-edge1") {
    name {
      value
    }
    interfaces {
      id
      name {
        value
      }
      description {
        value
      }
      role {
        name {
        	value
        }
      }
    }
  }
}
```
