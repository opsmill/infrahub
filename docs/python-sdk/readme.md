# Python SDK

A Python SDK for Infrahub greatly simplifies how we can interact with Infrahub programmatically.

## Installation

> The Python SDK is currently hosted in the same repository as Infrahub, but once both reach a better maturity state, the plan is to make it possible to install the SDK as a stand alone package.

For now, the recommendation is to clone the main Infrahub repository on your file system and to install the entire Infrahub package in your own repository using a relative path with the `--editable` flag.

```sh
poetry add --editable <path to the Infrahub repository on disk>
```

## Getting started

The SDK supports both synchronous and asynchronous Python. The default asynchronous version is provided by the `InfrahubClient` class while the synchronous version uses the `InfrahubClientSync` class.

### Dynamic schema discovery

By default, the Python client will automatically gather the active schema from Infrahub and all methods will generate based on that.

+++ Async

```python
from infrahub_sdk import InfrahubClient

client = await InfrahubClient.init(address="http://localhost:8000")
```

+++ Sync

```python
from infrahub_sdk import InfrahubClientSync

client = InfrahubClientSync.init(address="http://localhost:8000")
```

+++

### Authentication

The SDK is using a token-based authentication method to authenticate with the API and GraphQL.

The token can either be provided with `config=Config(api_token="TOKEN")` at initialization time or it can be retrieved automatically from the environment variable `INFRAHUB_SDK_API_TOKEN`.

> In the demo environment, the default token for the Admin account is `06438eb2-8019-4776-878c-0941b1f1d1ec`.

+++ Async

```python
from infrahub_sdk import InfrahubClient, Config

client = await InfrahubClient.init(config=Config(api_token="TOKEN"))
```

+++ Sync

```python
from infrahub_sdk import InfrahubClientSync, Config

client = InfrahubClientSync.init(config=Config(api_token="TOKEN"))
```

+++
