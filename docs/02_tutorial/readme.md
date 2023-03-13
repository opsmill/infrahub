# Tutorial Intro

This tutorial will get you started with Infrahub and it will help you get familiar with some of the main components and concepts behind Infrahub. To do that we'll use a sample dataset that represents a small network with 6 devices. This tutorial will teach you :
- How to query data via the GraphQL interface
- How to modify data via the REST API
- How to manage branches and query any branches
- How to query for past state via the GraphQL interface
- How to integrate a Git repository within Infrahub
- How to generate Jinja2 template
- How to expose your own API endpoint
- How to validate data within the CI/CD pipeline

> This tutorial doesn't require any prior knowledge, but a knowledge of Git, GraphQL and/or Python would be plus.

The tutorial is meant to be executed in order, as we'll be making some changes along the way that might be required later.

## Prepare the Demo Environment

### Build the demo environment locally

```
invoke demo.build
invoke demo.init
invoke demo.start
invoke demo.load-infra-schema
invoke demo.load-infra-data
```

The Web interface will be available at [http://localhost:3000](http://localhost:3000)
The GraphQL interface will be available at [http://localhost:8000/graphql](http://localhost:8000/graphql)
