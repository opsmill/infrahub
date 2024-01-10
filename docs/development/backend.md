---
title: Backend guide
icon: database
order: 90
---

# Backend guide

In order start developing on Infrahub backend, it is recommended to have a decent knowledge about topics such as Docker, Python and generally UNIX systems. Tools such as Docker and Python virtual environment help us in isolating the development work without interfering with the system itself. In this guide, we will use:

* [Python](https://www.python.org/) to be able to run the code
* [Invoke](https://www.pyinvoke.org/) to run some commands bundled with Infrahub
* [Poetry](https://python-poetry.org/) to manage our Python virtual environment
* [Docker](https://www.docker.com/) and its Compose extension to run dependencies such as the database, cache and queueing system

To fetch Infrahub's code, we will use git and we will use the `develop` branch.

```shell
git clone git@github.com:opsmill/infrahub.git
cd infrahub
git switch develop
```

## Basic settings

Most of Infrahub and tools around it rely on some settings. These settings are in general set as environment variables, dealing with many of these can be hard to maintain and manage. We can use a tool such as [direnv](https://direnv.net/) to help. It allows to define environment variables (or pretty much anything bash can make sense of) in a file that will be interpreted when entering a given directory. Here is an example of a `.envrc` file providing development friendly setting values:

```shell
export INFRAHUB_PRODUCTION=false
export INFRAHUB_SECURITY_SECRET_KEY=super-secret
export INFRAHUB_SDK_USERNAME=admin
export INFRAHUB_SDK_PASSWORD=infrahub
export INFRAHUB_SDK_TIMEOUT=20
export INFRAHUB_METRICS_PORT=8001
export INFRAHUB_DB_TYPE=memgraph # Accepts neo4j or memgraph
export INFRAHUB_SECURITY_INITIAL_ADMIN_TOKEN="${ADMIN_TOKEN}" # Random string which can be generated using: openssl rand -hex 16
export INFRAHUB_STORAGE_LOCAL_PATH="${HOME}/Development/infrahub-storage"
```

The exported environment variables are very important and must be set before moving to another step. Without these, you will likely face some errors or issues later.

## Required services

Infrahub uses several external services to work:

* A database such as neo4j or memgraph (faster for local development)
* A Redis in-memory store
* A RabbitMQ message broker

To run all these services, we will use Docker, but for local development some ports will need to be bound to local ones. To do so, a very basic Docker Compose override file is provided in the `development` directory, but it has a `tmp` extension which makes Compose ignore it by default. We will copy this file to a new one without the `tmp` extension. In a development environment, having only the services in Docker and Infrahub running on local Python is convenient to take advantage of the server auto-reload feature when making changes.

```shell
cp development/docker-compose.dev-override.yml.tmp development/docker-compose.dev-override.yml
```

Now we need to make sure we have a compatible version of Python that Infrahub can run on top of, Poetry to create virtual environment and Invoke to run commands. Invoke can be installed in many ways, but we recommend to use the `pipx` way to get it available user wide while without messing with the system Python. Assuming we have these utilities ready, we can run the following commands to build a proper Python environment:

```shell
cd infrahub # or the directory of your choice
poetry install
```

Now it's time to bring the required services up, and for that we have demo commands:

```shell
invoke demo.destroy demo.dev-start
```

This will actually pass two commands, one to destroy any remains of a previous run and one to start services. So this will effectively bring up clean services without leftovers. We can see which services are running by using:

```shell
poetry run invoke demo.status
```

This should yield a Docker output like the following:

```
NAME                       IMAGE                      COMMAND                  SERVICE         CREATED       STATUS                 PORTS
infrahub-cache-1           redis:7.2                  "docker-entrypoint.s…"   cache           2 hours ago   Up 2 hours (healthy)   0.0.0.0:6379->6379/tcp
infrahub-database-1        memgraph/memgraph:2.13.0   "/usr/lib/memgraph/m…"   database        2 hours ago   Up 2 hours (healthy)   0.0.0.0:7444->7444/tcp, 0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
infrahub-message-queue-1   rabbitmq:3.12-management   "docker-entrypoint.s…"   message-queue   2 hours ago   Up 2 hours (healthy)   4369/tcp, 5671/tcp, 0.0.0.0:5672->5672/tcp, 15671/tcp, 15691-15692/tcp, 25672/tcp, 0.0.0.0:15672->15672/tcp
```

When following a guide, like the [installation guide](../guides/installation.md), the command `demo.start` is mentioned. It is slightly different from the `demo.dev-start` that is mentioned here. The `demo.start` will bring up a demo environment as a whole including services and Infrahub while the `demo.dev-start` will only start the services as seen in the code block above.

## Running Infrahub test suite

With the required services working and properly setup Python virtual environment we can now run the Infrahub test suite to make sure the code works as intended.

```shell
INFRAHUB_LOG_LEVEL=CRITICAL pytest -v backend/tests/unit
```

The environment variable at the beginning of the command is useful to have a much more cleaner output when running tests.

## Running Infrahub server

We can run the Infrahub server with the built-in command:

```shell
infrahub server start --debug
```

The `debug` flag allows the server to be reloaded when a change is detected in the source code.

Note that this will only make the backend service usable, the frontend will not be available. Only the following URLs should work:

* http://localhost:8000/api/docs/
* http://localhost:8000/graphql

For running the frontend, please refer to its dedicated documentation [section](./frontend.md).

## Loading a new schema via CLI

For testing code changes, you may want to load a new schema from a YAML file. This can be performed in the development environment using:

```shell
poetry run infrahubctl schema load ${PATH_TO_SCHEMA_FILE}
```

## Code format

Formatting code in the backend relies on [Ruff](https://docs.astral.sh/ruff/) and [yamllint](https://yamllint.readthedocs.io/en/stable/). To ensure all files are as close as possible to the expected format, it is recommended to run the `format` command:

```shell
poetry run invoke format
```