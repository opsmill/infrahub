---
label: Architecture
layout: default
---
# Architecture diagram

![](../media/high_level_architecture.excalidraw.svg)

## Infrahub components

### API server

Language: Python

The API server delivers the REST API and the GraphQL endpoints.
Internally, the API server is built with FastAPI as the web framework and Graphene to generate the GraphQL endpoints.

!!!

Multiple instance of the API Server can run at the same time to process more requests.

!!!

### Git agent

Language: Python

The Git agent is responsible for managing all the content related to the Git repositories. It organizes the file systems in order to quickly access any relevant commit. The Git Agent periodically pulls the Git server for updates and listens to the RPC channel on the event bus for tasks to execute.

Some of the tasks that can be executed on the Git agent includes:

- Rendering a Jinja template.
- Rendering a transform function.
- Executing a check.
- All Git operations (pull/merge/diff).

!!!

Multiple instance of the Git agent can run at the same time to process more requests.

!!!

### Frontend

Language: React

## External systems

### Graph database

The Graph database is based on Bolt and Cypher. Currently, we have validated both Neo4j 5.x and Memgraph as possible options.
Neo4j is a production grade, battle tested graph database that is used in thousands of deployments around the world.
Memgraph is a lightweight, very fast, in-memory database that works great for testing and demos.

### Message bus

The message bus is based on RabbitMQ. It supports both a fanout channel to distribute messages to all members at the same time and a RPC framework to distribute work synchronously.

### Cache

The cache is based on Redis. It's mainly used as a central point to support the distributed lock systems between all the different component of the system.

### Git server (GitHub/GitLab)

Any Git server. The most popular being: GitHub, GitLab, or Bitbucket.
