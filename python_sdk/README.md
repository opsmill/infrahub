# Infrahub SDK

The Infrahub Python SDK greatly simplifies how you can interact with Infrahub programmatically.

Full documentation can be found in the [Infrahub Python SDK Documentation](https://docs.infrahub.app/python-sdk/).

## Installation

The Infrahub SDK can be installed using the pip package installer. It is recommended to install the SDK into a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install infrahub-sdk
```

### Installing optional extras

Extra's can be installed as part of the Python SDK and are not installed by default.

#### ctl

The ctl extra provides the infrahubctl command, which allows you to interact with an Infrahub instance.

```bash
pip install 'infrahub-sdk[ctl]'
```

#### tests

The tests extra provides all the components for the testing framework of Transforms, Queries and Checks.

```bash
pip install 'infrahub-sdk[tests]'
```

#### all

Installs infrahub-sdk together with all the extras.

```bash
pip install 'infrahub-sdk[all]'
```
