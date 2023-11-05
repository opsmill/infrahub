---
label: Demo Environment
layout: default
order: 100
---
# Local Demo Environment

A local environment based on Docker Composed is available for demo and testing.
It's designed to be controlled by `invoke` using a list of predefined commands

| Command               | Description                                                  | { class="compact" }
| --------------------- | ------------------------------------------------------------ |
| `demo.build`          | Build an image with the provided name and python version.    |
| `demo.init`           | (deprecated) Initialize Infrahub database before using it the first time. |
| `demo.start`          | Start a local instance of Infrahub within docker compose.    |
| `demo.stop`           | Stop the running instance of Infrahub.                       |
| `demo.destroy`        | Destroy all containers and volumes.                          |
| `demo.cli-git`        | Launch a bash shell inside the running Infrahub container.   |
| `demo.cli-server`     | Launch a bash shell inside the running Infrahub container.   |
| `demo.debug`          | Start a local instance of Infrahub in debug mode.            |
| `demo.status`         | Display the status of all containers.                        |
| `demo.load-infra-schema` | Load the infrastructure_base schema into Infrahub.   |
| `demo.load-infra-data` | Generate some data representing a small networks with 6 devices.   |

## Topology

| Container Name  | Image                    | Description                                            | { class="compact" }
| --------------- | ------------------------ | ------------------------------------------------------ |
| **database**        | memgraph/memgraph:2.11.0<br>or<br>neo4j:5.6-enterprise     | Graph Database   |
| **message-queue**   | rabbitmq:3.12-management | Message bus based on RabbitMQ                          |
| **cache**   | redis:7.2 | Cache based on Redis, mainly used for distributed lock                        |
| **infrahub-server** | Dockerfile               | Instance of the API Server, running GraphQL            |
| **infrahub-git**    | Dockerfile               | Instance of the Git Agent, managing the Git Repository |
| **frontend**        | Dockerfile               | Instance of the Frontend                               |

[!ref Check the architecture diagram to have more information about each component](./architecture.md)

## Getting Started

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

## Advanced Settings

### Support for `sudo`

On a linux system, the system will try to automatically detect if `sudo` is required to run the docker command or not.

It's possible to control this setting with the environment variable: `INVOKE_SUDO`

```
export INVOKE_SUDO=1 to force sudo
export INVOKE_SUDO=0 to disable it completely
```

### Support for `pty`

On Linux and Mac OS, all commands will be executed with PTY enabled by default.

It's possible to control this setting with the environment variable: `INVOKE_PTY`

```
export INVOKE_PTY=1 to force pty
export INVOKE_PTY=0 to disable it completely
```

## Troubleshooting

At First, it's recommended to check if all containers are still running using `invoke demo.status`. The 5 containers should be running and be present.
- If one is not running, you can try to restart it with `invoke demo.start`
- If the container is still not coming up, you can watch the logs with `docker logs <container name>` (the container name will include the name of the project and a number like `infrahub-dev-infrahub-git-1` )

If some containers are still not coming up, it's recommanded to start from a fresh install with `invoke demo.destroy`.