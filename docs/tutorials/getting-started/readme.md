# Getting started with Infrahub

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

### Pre-Requisite

In order to run the demo environment, the following applications must be installed on the systems:
- [pyinvoke](https://www.pyinvoke.org/)
- Docker & Docker Compose

> On a Laptop, both Docker & Docker Compose can be installed by installing [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### First utilization

Before the first utilization you need to build the images for Infrahub with the command:
```
invoke demo.build
```
Initialize the database and start the application
```
invoke demo.start
```

### Load some data

Once you have an environment up and running you can load your own schema or you can explore the one provided with the project using the following commands.
```
invoke demo.load-infra-schema
invoke demo.load-infra-data
```

### Control the local environment

- `invoke demo.start` : Start all the containers in detached mode.
- `invoke demo.stop` : Stop All the containers
- `invoke demo.destroy` : Destroy all containers and volumes.


!!!
`invoke demo.debug` can be used as an alternative to `invoke demo.start`, the main difference is that it will stay *attached* to the containers and all the logs will be displayed in real time in the CLI.
!!!

## User Accounts available for the tutorial

Multiple user accounts with different levels of permissions are available.
To follow the tutorial you should use the `admin` account but you can try the other accounts too to see how the interface behaves with different permission levels.

| name          | username        | password      | role       |
| ------------- | --------------- | ------------- | ---------- |
| Administrator | `admin`         | `infrahub`    | admin      |
| Chloe O'Brian | `Chloe O'Brian` | `Password123` | read-write |
| David Palmer  | `David Palmer`  | `Password123` | read-only  |

> The default token for the Admin account is `06438eb2-8019-4776-878c-0941b1f1d1ec`
> While using the API the Authentication Token must be provided in a header named `X-INFRAHUB-KEY`

[!ref Access the Web interface](http://localhost:8000)
[!ref Access the GraphQL interface](http://localhost:8000/graphql)
