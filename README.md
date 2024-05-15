<!-- markdownlint-disable -->
![Infrahub Logo](docs/static/img/infrahub-hori.svg)
<!-- markdownlint-restore -->

# Infrahub [![CI](https://github.com/opsmill/infrahub/actions/workflows/ci.yml/badge.svg?branch=stable)](https://github.com/opsmill/infrahub/actions/workflows/ci.yml)

Infrahub from [OpsMill](https://opsmill.com) is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run. Infrahub offers a central hub to manage the data, templates and playbooks that power your infrastructure by combining the version control and branch management capabilities of Git with the flexible data model and UI of a graph database.

## Quick Start

Leveraging [GitHub Codespaces](https://docs.github.com/en/codespaces/overview), it's possible to start a new instance of Infrahub in the Cloud in minutes:

|  No Data | Demo Data |
|---|---|
| [![Launch in GitHub Codespaces (No Data)](https://img.shields.io/badge/Launch%20Infrahub-0B6581?logo=github)](https://codespaces.new/opsmill/infrahub?devcontainer_path=.devcontainer%2Fdevcontainer.json&ref=stable) | [![Launch in GitHub Codespaces (Demo Data)](https://img.shields.io/badge/Infrahub%20with%20Data-0B6581?logo=github)](https://codespaces.new/opsmill/infrahub?devcontainer_path=.devcontainer%2Fdevcontainer.json&ref=stable) |

To deploy a local instance of Infrahub please refer to our guide: [Installing Infrahub](https://docs.infrahub.app/guides/installation)

## Documentation

If you'd like to learn more about Infrahub, please refer to the following resources:

- [Infrahub Overview](https://docs.infrahub.app/tutorials/infrahub-overview/)
- [Getting Started](https://docs.infrahub.app/tutorials/getting-started/)
- [Infrahub Documentation](https://docs.infrahub.app/)

## Project status

Infrahub is currently in in open beta, which means that not all features we are targeting for the first major release have been implemented yet and the project is still evolving at a very rapid pace. For upcoming development plans, see our [public roadmap](https://opsmill.atlassian.net/jira/discovery/share/views/7e5d4ab1-63d7-405e-b453-ad50cd9d5b71)

## Support and Community

If you need help, support for the open-source Infrahub project is provided on [![Join our Discord server](https://img.shields.io/badge/Discord-7289DA?logo=discord&logoColor=white)](https://discord.gg/jXMRp9hXSX) or via [filing an issue on GitHub](https://github.com/opsmill/infrahub/issues)

## Contributing

[View our CONTRIBUTING](./CONTRIBUTING.md) policy to find the latest information.

## Telemetry Data Collection

By default, Infrahub collects the following non-user-identifying telemetry data:

- Up/Down status of services
- Number of Nodes
- Number of Objects Created
- Count of Branches Created
- Count of Branches not yet merged
- Number of Resource Pools
- Obfuscated Schema Summary
- Infrahub Version
- Number of GIT repos
- Number of workers
- Number of generators
- Number of artifact definitions
- Number of times artifacts are being generated
- Number of transformation
- Number of groups
- Number of profiles
- Number of webhooks
- Number of times webhooks are fired

To disable telemetry on Infrahub deployment, set the following environmental variable:

```bash
export INFRAHUB_TELEMETRY_OPTOUT=true
```

## Security

[View our SECURITY](./SECURITY.md) policy to find the latest information.
