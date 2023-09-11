
# Build a local Environment

The project includes a local demo environment that can be used to explore or demo Infrahub.

The main requirements to run the Sandbox environment are:
- [Invoke](https://www.pyinvoke.org) (version 2 minimum)
- [Docker & Docker Compose](https://docs.docker.com/engine/install/)

## Prepare the Local Environment

```
invoke demo.build
invoke demo.init
```

You can then start all the services with

```
invoke demo.start
```

[!ref Access the Web interface](http://localhost:8000)
[!ref Access the GraphQL interface](http://localhost:8000/graphql)


# Explore Infrahub with some Infrastructure Data

A demo dataset representing a simple 6 nodes network is available to explore Infrahub with some meaningful data.
You can load the demo data and its associated schema with the following commands.

```
invoke demo.load-infra-schema
invoke demo.load-infra-data
```

To explore further, [a tutorial](../02_tutorial/readme.md) is available to guide you through the application and the GraphQL interface.


[!ref Check the documentation of the demo environment for more information](../20_knowledge_base/local_demo_environment.md)
