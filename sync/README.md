<!-- markdownlint-disable -->
![Infrahub Logo](https://assets-global.website-files.com/657aff4a26dd8afbab24944b/657b0e0678f7fd35ce130776_Logo%20INFRAHUB.svg)
<!-- markdownlint-restore -->

# Infrahub by OpsMill

[Infrahub](https://github.com/opsmill/infrahub) by [OpsMill](https://opsmill.com) is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run.

At its heart, Infrahub is built on 3 fundamental pillars:

- **Powerful Schema**: that's easily extensible
- **Unified Version Control**: for data and files
- **Data Synchronization**: with traceability and ownership

## Infrahub Sync

Infrahub-Sync is a versatile Python package that synchronizes data between a source and a destination system. It builds on the robust capabilities of `diffsync` to offer flexible and efficient data synchronization across different platforms, including Netbox, Nautobot, and Infrahub. This package features a Typer-based CLI for ease of use, supporting operations such as listing available sync projects, generating diffs, and executing sync processes.

### Features

- **Multiple Systems Support**: Synchronize data between Netbox, Nautobot, and Infrahub.
- **Flexible Configuration**: Define synchronization tasks with YAML configuration files.
- **CLI Interface**: Manage sync tasks directly from the command line.
- **Custom Sync Logic**: Generate Python code for custom sync adapters and models using provided Jinja templates.

### Requirements

Requirements

- The two latest Infrahub releases
- Python >=3.9, <3.13
- Python modules:
  - infrahub-sdk >= 0.9.0

## Project Structure

```bash
.
├── README.md
├── examples
│   ├── nautobot-v1_to_infrahub
│   │   ├── config.yml
│   │   ├── infrahub
│   │   │   ├── __init__.py
│   │   │   ├── sync_adapter.py
│   │   │   └── sync_models.py
│   │   └── nautobot
│   │       ├── __init__.py
│   │       ├── sync_adapter.py
│   │       └── sync_models.py
│   ├── nautobot-v2_to_infrahub
│   │   ├── config.yml
│   │   ├── infrahub
│   │   │   ├── __init__.py
│   │   │   ├── sync_adapter.py
│   │   │   └── sync_models.py
│   │   └── nautobot
│   │       ├── __init__.py
│   │       ├── sync_adapter.py
│   │       └── sync_models.py
│   └── netbox_to_infrahub
│       ├── config.yml
│       ├── infrahub
│       │   ├── __init__.py
│       │   ├── sync_adapter.py
│       │   └── sync_models.py
│       └── netbox
│           ├── __init__.py
│           ├── sync_adapter.py
│           └── sync_models.py
├── infrahub-sync
│   ├── infrahub_sync
│   │   ├── __init__.py
│   │   ├── adapters
│   │   │   ├── infrahub.py
│   │   │   ├── nautobot.py
│   │   │   └── netbox.py
│   │   ├── cli.py
│   │   ├── generator
│   │   │   ├── __init__.py
│   │   │   ├── templates
│   │   │   │   ├── diffsync_adapter.j2
│   │   │   │   └── diffsync_models.j2
│   │   │   └── utils.py
│   │   └── utils.py
│   └── tests
│       └── __init__.py
├── poetry.lock
├── potenda
│   └── potenda
│       └── __init__.py
└── pyproject.toml
```

## Documentation

If you'd like to learn more, please check out the documentation:

|  | Branch `stable` | Branch `develop` |
|---|---|---|
| Documentation | [![Documentation](https://img.shields.io/badge/Documentation%20for%20stable-0B97BB?style=for-the-badge)](https://docs.infrahub.app/) | [![Documentation](https://img.shields.io/badge/Documentation%20for%20develop-0B97BB?style=for-the-badge)](https://develop.infrahub.pages.dev/) |
