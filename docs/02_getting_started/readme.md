
# Build a local Environment

The project includes a local demo environment that can be used to experiment and/or demo Infrahub.

The main requirements to run the Sandbox environment are:
- Invoke (version 2 minimum) on MacOS `% brew install pyinvoke`
- Docker & Docker Compose

## Prepare the Local Environment

```
invoke demo.build
invoke demo.init
```

You can then start all the services with

```
invoke demo.start
```

[!ref Access the Web interface](http://localhost:3000)
[!ref Access the GraphQL interface](http://localhost:8000/graphql)


# Explore Infrahub with some Infrastructure Data

A demo dataset representing a simple 6 nodes network is available to explore Infrahub with some meaningful data.
You can load the demo data and its associated schema with the following commands.

```
invoke demo.load-infra-schema
invoke demo.load-infra-data
```

To explore further, [a tutorial](../02_tutorial/readme.md) is available to guide you through the application and the GraphQL interface.


[!ref Check the documentation of the demo environment for more information](../20_knowledge_base/80_local_demo_environment.md)
