# Python SDK

A Python SDK for Infrahub greatly simplifies how we can interact with Infrahub programmatically.

!!!warning :zap: **Disclaimer** :zap:
The Python Client is still under development and it doesn't have 100% feature parity with the GraphQL API yet.
!!!

## Installation

> The Python SDK is currently hosted in the same repository as infrahub, but once both reaches a better maturity state, the plan is to make it easy to install the SDK as a stand alone package.

## Getting Started

The SDK supports both synchronous and asynchronous Python. The default asynchronous version is provided by the `InfrahubClient` class while the synchronous version
is using the `InfrahubClientSync` class.

### Query all Account objects

:::code source="../../python_sdk/examples/example_query_all.py" :::

### Create a new Account

:::code source="../../python_sdk/examples/example_create.py" :::


### Update an existing object

:::code source="../../python_sdk/examples/example_update.py" :::

### Delete an object

:::code source="../../python_sdk/examples/example_delete.py" :::

### Create a new Account with the synchronous version

:::code source="../../python_sdk/examples/example_create_sync.py" :::
