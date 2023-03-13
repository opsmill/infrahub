---
label: GraphQL Mutation
# icon: file-directory
tags: [tutorial]
order: 900
---

GraphQL Mutations are available to create, update or delete any objects in the database. In a REST API they are the equivalent of a the methods POST, PUT or DELETE.

```graphql # Create a new organization
# Endpoint : http://localhost:8000/graphql/main
mutation {
  organization_create(
    data: {
      name: { value: "Hooli" },
      description: { value: "Transforming the world as we know it."}
    }
  ) {
    ok
    object {
      id
    }
  }
}
```