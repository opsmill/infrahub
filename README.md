<h1 align="center">
  <a href=""><img src="docs/static/img/infrahub-hori.svg" alt="Infrahub" width="350"></a>
</h1>
<h3 align="center">Simplify Infrastructure Automation</h2>

<p align="center">
<a href="https://www.linkedin.com/company/opsmill">
<img src="https://img.shields.io/badge/linkedin-blue?logo=linkedin"/>
</a>
<a href="https://discord.gg/opsmill">
<img src="https://img.shields.io/badge/Discord-7289DA?&logo=discord&logoColor=white"/>
</a>
</p>

Infrahub from [OpsMill](https://opsmill.com) is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run. Infrahub offers a central hub to manage the data, templates and playbooks that powers your infrastructure by combining the version control and branch management capabilities similar to Git with the flexible data model and UI of a graph database.

If you just want to try Infrahub out, you can use our [Infrahub Sandbox](https://sandbox.infrahub.app/) to get started.

![infrahub screenshot](docs/docs/media/infrahub-readme.gif)

## Why Use Infrahub?

**Unified Source of Truth** - Infrahub is a single source of truth for all your infrastructure and network data. It provides a unified view of your infrastructure, allowing you to manage your infrastructure in a more efficient and effective way. Infrahub allows unidirectional and bi-directional [data synchronization](https://docs.infrahub.app/sync/sync/) between other internal systems and Infrahub. The data can be accessed via WebUI, API and SDK, along with SSO and RBAC for access control.

**Flexible Schema** - Infrahub provides a flexible schema for your infrastructure data and related business information, allowing you to define your own data model and customize it to your needs. Get started quickly with our [schema library](https://github.com/opsmill/schema-library) or build your own.

**Version Control** - Infrahub provides a version control system for your infrastructure data, allowing you to track changes and revert to previous versions if needed. Immutable history of all changes to the data and artifacts is maintained, allowing you to audit and review changes to your infrastructure.

**CI Pipeline and Validation** - Infrahub provides a CI pipeline and validation system for your infrastructure data, allowing you to ensure that your infrastructure is always in a valid state. Infrahub was designed with infrastructure-as-code workflows in mind, removing fragility and complexity of combining together multiple tools and projects to achieve the same goal.

## Infrahub Use Cases

**Service Catalog** - Infrahub acts as the underlying system to provide infrastructure-as-a-service, allowing you to manage your services and lifecycle them as the services evolve.

**Infrastructure Automation** - Provide infrastructure and network automation workflows with Infrahub rendering configurations and artifacts via Jinja2 and python,then passing to deployment tools such as [Nornir](https://www.opsmill.com/simplifying-network-automation-workflows-with-infrahub-nornir-and-jinja2/), [Ansible](https://docs.infrahub.app/ansible/ansible/), Terraform, or vendor-specific tools.

**Inventory Management** - Infrahub serves as a centralized inventory system for your infrastructure, allowing you to manage your inventory and track changes to your infrastructure. It provides a WebUI and API for other teams to self-service the information needed to allow the organization to operate.

**DCIM and IPAM** - Infrahub provides centralized DCIM and IPAM systems for your infrastructure, capable of handling complex cases such as overlapping IP addresses and VLANs, automation-friendly, branch-aware allocation of resources via Infrahub's [Resource Manager](https://docs.infrahub.app/python-sdk/guides/resource-manager), and more.

## Quick Start

[Infrahub Sandbox](https://sandbox.infrahub.app/) - Instantly login to the UI of a demo environment of Infrahub with sample data pre-loaded.

[Getting Started Environment & Tutorial](https://opsmill.instruqt.com/pages/labs) - It spins up an instance of Infrahub on our cloud, provides a browser, terminal, code editor and walks you through the basic concepts:

- Branching and version control
- Flexible schema
- Unified storage

For longer term tests, you can deploy a local instance of Infrahub by referring to our guide: [Installing Infrahub](https://docs.infrahub.app/guides/installation)

## Documentation

If you'd like to learn more about Infrahub, please refer to the following resources:

- [Infrahub Overview](https://docs.infrahub.app/overview/)
- [Infrahub Documentation](https://docs.infrahub.app/)
- [FAQ](https://docs.infrahub.app/faq/)

## Support and Community

If you need help, support for the community version of Infrahub is provided on [![Join our Discord server](https://img.shields.io/badge/Discord-7289DA?logo=discord&logoColor=white)](https://discord.gg/opsmill) or via [filing an issue on GitHub](https://github.com/opsmill/infrahub/issues).

## Contributing

To help our community with the creation of contributions, please view our [CONTRIBUTING](./CONTRIBUTING.md) page.

<a  href="https://github.com/opsmill/infrahub/graphs/contributors">
<img  src="https://contrib.rocks/image?repo=opsmill/infrahub" />
</a>

## Security

[View our SECURITY](https://github.com/opsmill/infrahub?tab=security-ov-file) policy to find the latest information.
