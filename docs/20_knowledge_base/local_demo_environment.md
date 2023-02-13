
# Local Demo Environment

A local environment based on Docker Composed is available for demo and testing.
It's designed to be controlled by `invoke` using a list of predefined commands

| Command          | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| `build`          | Build an image with the provided name and python version.    |
| `init`           | Initialize Infrahub database before using it the first time. |
| `load-demo-data` | Launch a bash shell inside the running Infrahub container.   |
| `start`          | Start a local instance of Infrahub within docker compose.    |
| `stop`           | Stop the running instance of Infrahub.                       |
| `destroy`        | Destroy all containers and volumes.                          |
| `cli-git`        | Launch a bash shell inside the running Infrahub container.   |
| `cli-server`     | Launch a bash shell inside the running Infrahub container.   |
| `debug`          | Start a local instance of Infrahub in debug mode.            |
| `status`         | Display the status of all containers.                        |

## Topology

| Container Name  | Image                    | Description                                            |
| --------------- | ------------------------ | ------------------------------------------------------ |
| database        | neo4j:5.1-enterprise     | Graph Database                                         |
| message-queue   | rabbitmq:3.11-management | Message bus based on RabbitMQ                          |
| infrahub-server | Dockerfile               | Instance of the API Server, running GraphQL            |
| infrahub-git    | Dockerfile               | Instance of the Git Agent, managing the Git Repository |

## Getting Started

### First utilization

Before the first utilization you need to build the image for the infrahub containers with the command 
```
invoke build
```
Initialize the database and load some data
```
invoke init
invoke load-demo-data
```

> It's possible to execute both commands at once with `invoke init load-demo-data`

### Control the local environment


- `invoke start` : Start all the containers in detached mode.
- `invoke stop` : Stop All the containers
- `invoke destroy` : Destroy all containers and volumes.


> `invoke debug` can be used as an alternative to `invoke start`, the main difference is that it will stay *attached* to the containers and all the logs will be displayed in real time in the CLI.


## Troubleshooting

First, it's recommended to check if all containers are still running using `invoke status`. The 4 containers should be running and be present.
- If one is not running, you can try to restart it with `invoke start`
- If the container is still not coming up, you can watch the logs with `docker logs <container name>` (the container name will include the name of the project and a number like `infrahub-dev-infrahub-git-1` )

If some containers are still not coming up, it's recommanded to start from a fresh install with `invoke destroy`.