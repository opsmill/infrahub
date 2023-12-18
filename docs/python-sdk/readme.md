# Python SDK

A Python SDK for Infrahub greatly simplifies how we can interact with Infrahub programmatically.

## Installation

The Infrahub SDK for Python is available on [PyPI](https://pypi.org/project/infrahub-sdk/) and can be installed using the `pip` package installer. It is recommended to install the SDK into a virtual environment.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install infrahub-sdk
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
