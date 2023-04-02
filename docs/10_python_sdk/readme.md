# Python SDK

A Python SDK for Infrahub greatly simplifies how we can interact with Infrahub programmatically.

!!!warning :zap: **Disclaimer** :zap:
The Python Client is still under development and it doesn't have 100% feature parity with the GraphQL API yet.
!!!

!!!warning Async Version Only
It's important to mention that the current version of the Python SDK is only compatible with Python Async.
The goal is to support both Sync and Async Python but currently, it only supports Async.  
Please reach out if you need help getting started with Python Async, it's easier than it looks.<br>
_There are a few examples of scripts available to help you get started as an example._<br>
_If this is a big show-stopper for you, please let us know so that we can prioritize the work to add support for non-async python._
!!!

## Installation

> The Python SDK is currently hosted in the same repository as infrahub, but once both reaches a better maturity state, the plan is to move the SDK into its own repository.

## Getting Started

### Query all Account objects

:::code source="../../python_sdk/examples/example_query_all.py" :::

### Create a new Account

:::code source="../../python_sdk/examples/example_create.py" :::


### Update an existing object

:::code source="../../python_sdk/examples/example_update.py" :::

### Delete an object

!!!
Not supported yet
!!!