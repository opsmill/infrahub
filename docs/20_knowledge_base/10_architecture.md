---
label: Architecture
layout: default
order: 900
---
# Architecture Diagram

![](../media/high_level_architecture.excalidraw.svg)

## Infrahub Components

### API Server

Language: Python

The API Server is serving the REST API and the GraphQL endpoints.
Internally the API Server is built with FastAPI as the web framework and Graphene to generate the GraphQL endpoints.

!!!
Multiple instance of the API Server can run at the same time to process more requests.
!!!

### Git Agent

Language: Python

The Git agent is responsible for managing all the content related to the Git repositories, it organizes the file systems in order to quickkly access any relevant commit. The Git Agent is periodically pulling the Git Server for updates and it's listening to the RPC channel on the event bus for tasks to execute.
Some of the tasks that can be executed on the Git agent includes:
- Rendering a Jinja template
- Rendering a transform function
- Executing a check
- All Git operations (pull/merge/diff)

!!!
Currently only one instance of the Git Agent can run at a time.
!!!

### Frontend

Language: React

## External Systems

### Graph Database

The Graph Database is based on Neo4j 5.x.
Neo4j is a production grade, battle tested graph database that is used in 1000s of deployments around the world.

### Message Bus

The message bus is based on RabbitMQ, it supports both a fanout channel to distribute messages to all members at the same time and a RPC framework to distribute work Syncronously.

### Git Server (Github/Gitlab)

Any Git server. The most popular being : GitHub, GitLab or Bitbucket