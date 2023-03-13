
# Build a local Sandbox Environment

The project includes a local sandbox environment that can be used to experiment and/or demo Infrahub.
The main requirements to run the Sandbox environment are :
- Invoke 2.x
- Docker & Docker Compose

## Prepare the Sandbox Environment

```
invoke demo.build
invoke demo.init
```

You can then start all the services with

```
invoke demo.start
```

The Web interface will be available at [http://localhost:3000](http://localhost:3000)
The GraphQL interface will be available at [http://localhost:8000/graphql](http://localhost:8000/graphql)

# Explore Infrahub with some Infrastructure Data

A demo dataset representing a simple 6 nodes network is available to explore Infrahub with some meaningful data.
You can load the demo data and its associated schema with the following commands.

```
invoke demo.load-infra-schema
invoke demo.load-infra-data
```

To explore further, [a tutorial](../02_tutorial/readme.md) is available to guide you through the application and the graphQL interface.