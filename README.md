

# InfraHub

> The project is under active development and as such it's evolving very rapidly. 
The best documentation right now is the code itself, when the code will stabilize it will be a good time to build a proper documentation.

## Getting Started

Infrahub is a Python project (3.8+) and it requires an running instance of Neo4J.

```
poetry install
```

### Build a demo environment

Start Neo4J
```
invoke neo4j-start
```

Initialize the database and load some data
```
infrahub db init
infrahub db load-test-data --dataset dataset03
```

Start the main services
```
gunicorn infrahub.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
infrahub worker start
```

The graphQL interface will be available at `http://localhost:8000/graphql`

## Development Environment

In development mode, it's recommended to start the webserver in dev mode instead of using GUNICORN

```
infrahub server start --debug
```

# Tests

```
infrahub test unit
infrahub test integration
```
or
```
infrahub test unit <path>
```
