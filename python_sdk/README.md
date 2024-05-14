<!-- markdownlint-disable -->
![Infrahub Logo](https://assets-global.website-files.com/657aff4a26dd8afbab24944b/657b0e0678f7fd35ce130776_Logo%20INFRAHUB.svg)
<!-- markdownlint-restore -->

# Infrahub by OpsMill

[Infrahub](https://github.com/opsmill/infrahub) by [OpsMill](https://opsmill.com) is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run.

At its heart, Infrahub is built on 3 fundamental pillars:

- **Powerful Schema**: that's easily extensible
- **Unified Version Control**: for data and files
- **Data Synchronization**: with traceability and ownership

## Infrahub SDK

The Infrahub Python SDK greatly simplifies how you can interact with Infrahub programmatically.

More information can be found in the [Infrahub Python SDK Documentation](https://docs.infrahub.app/python-sdk/).

## Installation

The Infrahub SDK can be installed using the pip package installer. It is recommended to install the SDK into a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install infrahub-sdk
```

### Installing optional extras

Extras can be installed as part of the Python SDK and are not installed by default.

#### ctl

The ctl extra provides the `infrahubctl` command, which allows you to interact with an Infrahub instance.

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
