---
icon: terminal
---
# Installing Infrahub

Infrahub is composed of multiple components. The backend is mostly written in Python and the frontend in React.

The main components are:

- A **Frontend** written in react.
- An **API server** written in Python with FastAPI.
- A **Git agent** to manage the interaction with external Git repositories.
- A **Graph database** based on `Neo4j` 5.x or `memgraph`.
- A **Message bus** based on `RabbitMQ`.

## Docker Compose

The recommended way to run Infrahub is to use the Docker Compose project included with the project combined with the helper commands defined in `invoke`.

The pre-requisites for this type of deployment are to have:

- [Invoke](https://www.pyinvoke.org) (version 2 minimum) and TOML
- [Docker](https://docs.docker.com/engine/install/) (version 24.x minimum)

+++ MacOS

### Invoke

On MacOS, Python is installed by default so you should be able to install `invoke` directly.
Invoke works best when you install it in the main Python environment, but you can also install it in a virtual environment if you prefer. To install `invoke` and `toml`, run the following command:

```sh
pip install invoke toml
```

### Docker

To install Docker, follow the [official instructions on the Docker website](https://docs.docker.com/desktop/install/mac-install/) for your platform.

+++ Windows

On Windows, install a Linux VM via WSL2 and follow the installation guide for Ubuntu.

!!!
The native support on Windows is currently under investigation and is being tracked in [issue 794](https://github.com/opsmill/infrahub/issues/794).
Please add a comment to the issue if this is something that would be useful to you.
!!!

+++ Ubuntu

!!!warning
On Ubuntu, depending on which distribution you're running, there is a good chance your version of Docker might be outdated. Please ensure your installation meets the version requirements mentioned below.
!!!

### Invoke

Invoke is a Python package commonly installed by running `pip install invoke toml`.
If Python is not already installed on your system, install it first with `sudo apt install python3-pip`.

### Docker

Check if Docker is installed and which version is installed with `docker --version`
The version should be at least `24.x`. If the version is `20.x`, it's recommended to upgrade.

[This tutorial (for Ubuntu 22.04) explains how to install the latest version of docker on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-22-04).

+++ Other

The deployment should work on any systems that can run a modern version of Docker and Python.

Please reach out if you need some help and feel free to send a PR with the installation instructions for your platform.

+++

Once docker desktop and invoke are installed you can build, start, and initialize the Infrahub demo environment with the following command:

```sh
invoke demo.build demo.start demo.load-infra-schema demo.load-infra-data
```

[!ref Check the documentation of the demo environment for more information](../topics/local-demo-environment.md)

## GitPod

The project is also pre-configured to run in GitPod.

!!!
GitPod provides a Cloud Development Environment that allows you to run any project right within your browser.
!!!

GitPod has a generous free tier of 50/hours per month for free.
> For our early testers, we also provide access to our GitPod organization which includes some credits and some pre-built environments to speedup the deployment time.

[!ref Check Infrahub in GitPod](https://gitpod.io/#/github.com/opsmill/infrahub)

## K8s with Helm charts

Support for K8s is not yet available, but we are actively tracking this effort in our short/mid-term roadmap. You can follow [this issue for updates](https://github.com/opsmill/infrahub/issues/506).

Please reach out and let us know if you are interested in this feature. It helps us prioritize what the team needs to focus on.
