# Tutorial Intro

This tutorial will get you started with Infrahub and it will help you get familiar with some of the main components and concepts behind Infrahub. To do that we'll use a sample dataset that represents a small network with 6 devices. This tutorial will teach you :
- How to manage branches and query any branches
- How to integrate a Git repository within Infrahub
- How to generate Jinja2 template
- How to expose a new Data Transformation endpoint
- How to validate data within the CI/CD pipeline
- How to extend the current schema
- How to query data via the GraphQL interface
- How to modify data via the REST API
- How to query for past state via the GraphQL interface


> This tutorial doesn't require any prior knowledge, but knowledge of Git, GraphQL and Python will make things easier to understand.

The tutorial is meant to be executed in order, as we'll be making some changes along the way that might be required later.

## Prepare the Demo Environment

### Build the demo environment locally

```
invoke demo.build
invoke demo.init
invoke demo.start
```

### User Accounts available for the tutorial

Multiple user accounts with different levels of permissions are available.
To follow the tutorial you should use the `admin` account but you can try the other accounts too to see how the interface behaves with different permission levels.

| name          | username        | password      | role       |
|---------------|-----------------|---------------|------------|
| Administrator | `admin`         | `infrahub`    | admin      |
| Chloe O'Brian | `Chloe O'Brian` | `Password123` | read-write |
| David Palmer  | `David Palmer`  | `Password123` | read-only  |

> The default token for the Admin account is `06438eb2-8019-4776-878c-0941b1f1d1ec`  
> While using the API the Authentication Token must be provided in a header named `X-INFRAHUB-KEY`

[!ref Access the Web interface](http://localhost:3000)
[!ref Access the GraphQL interface](http://localhost:8000/graphql)
