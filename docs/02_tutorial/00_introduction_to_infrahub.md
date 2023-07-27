---
label: Introduction to Infrahub
# icon: file-directory
tags: [tutorial]
order: 900
---

Before starting this tutorial, let's take a moment to explore how Infrahub is organized as an application and how we can interact with it.

## Infrahub Components

![](../media/high_level_architecture.excalidraw.svg)

During this tutorial we'll mainly use the Frontend, the `infrahubctl` CLI and GraphQL via the API Server.

| Name | Description | Demo Environment | { class="compact" }
|---|---|---|
| **infrahubctl** | Command line utility to interact with Infrahub and manage some core objects like the branches or the schema. | `invoke demo.cli-git` |
| **Frontend** | Main User interface |  [http://localhost:8000](http://localhost:8000) |
| **API Server** | GraphQL and REST API server, primary component to interact with the data. |  [http://localhost:8000/graphql](http://localhost:8000/graphql) |
| **Git Agent** | Infrahub Agent that manages all content hosted in Git.  |  -- |
| **Git Server** | External Git Server like Github or Gitlab that can host some Git repositories  |  |
| **GraphDB** | Main database where all information in the graph are stored. Neo4j 5.x | -- |
| **Message Bus** | Message bus based on RabbitMQ to allow all components to interact |-- |
