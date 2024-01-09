---
icon: terminal
order: 1000
---
# Installing Infrahub

Infrahub is composed of multiple components. The backend is mostly written in Python and the frontend in React.

The main components are:

- A **Frontend** written in react.
- An **API server** written in Python with FastAPI.
- A **Git agent** to manage the interaction with external Git repositories.
- A **Graph database** based on `Neo4j` 5.x or `memgraph`.
- A **Message bus** based on `RabbitMQ`.

Refer to [Architecture](/topics/architecture) for a more in-depth view of the components interaction.

## From Git repository

Create the base directory for the Infrahub installation. For this guide, we'll use /opt/infrahub.

```sh
sudo mkdir -p /opt/infrahub/
cd /opt/infrahub/
```

Next, clone the `stable` branch of the Infrahub GitHub repository into the current directory. (This branch always holds the current stable release.)

```sh
git clone -b stable --depth 1 git@github.com:opsmill/infrahub.git .
```

!!!note
The command above utilizes a "shallow clone" to retrieve only the most recent commit. If you need to download the entire history, omit the --depth 1 argument.
!!!

The `git clone` command should generate output similar to the following:

```sh
Cloning into '.'...
remote: Enumerating objects: 1312, done.
remote: Counting objects: 100% (1312/1312), done.
remote: Compressing objects: 100% (1150/1150), done.
remote: Total 1312 (delta 187), reused 691 (delta 104), pack-reused 0
Receiving objects: 100% (1312/1312), 33.37 MiB | 14.46 MiB/s, done.
Resolving deltas: 100% (187/187), done.
```

### Docker Compose

The recommended way to run Infrahub is to use the Docker Compose files included with the project combined with the helper commands defined in `invoke`.

The pre-requisites for this type of deployment are to have:

- [Invoke](https://www.pyinvoke.org) (version 2 minimum)
- [Toml](https://toml.io/en/)
- [Docker](https://docs.docker.com/engine/install/) (version 24.x minimum)

+++ MacOS

#### Invoke

On MacOS, Python is installed by default so you should be able to install `invoke` directly.
Invoke works best when you install it in the main Python environment, but you can also install it in a virtual environment if you prefer. To install `invoke` and `toml`, run the following command:

```sh
pip install invoke toml
```

#### Docker

To install Docker, follow the [official instructions on the Docker website](https://docs.docker.com/desktop/install/mac-install/) for your platform.

+++ Windows

On Windows, install a Linux VM via WSL2 and follow the installation guide for Ubuntu.

!!!warning
The native support on Windows is currently under investigation and is being tracked in [issue 794](https://github.com/opsmill/infrahub/issues/794).
Please add a comment to the issue if this is something that would be useful to you.
!!!

+++ Ubuntu

!!!warning
On Ubuntu, depending on which distribution you're running, there is a good chance your version of Docker might be outdated. Please ensure your installation meets the version requirements mentioned below.
!!!

#### Invoke

Invoke is a Python package commonly installed by running `pip install invoke toml`.
If Python is not already installed on your system, install it first with `sudo apt install python3-pip`.

#### Docker

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

[!ref Check the documentation of the demo environment for more information](/topics/local-demo-environment.md)

<!-- vale off -->
### GitHub Codespace
<!-- vale on -->
The project is pre-configured to run in GitHub Codespace. We have two devcontainer configuration:

- Infrahub: bare-bones container with the app running without any [Schema extension](/tutorials/getting-started/schema) or data
- Infrahub-demo: container running the [demo environment](/topics/local-demo-environment.md)

The default devcontainer `.devcontainer/devcontainer.json` is the bare-bones one. If you want to run the demo, you will need to choose it in your GitHGub Codespace options.

[!ref Infrahub devcontainer file](https://github.com/opsmill/infrahub/tree/stable/.devcontainer/devcontainer.json)

## GitPod

The project is also pre-configured to run in GitPod.

!!!
GitPod provides a Cloud Development Environment that allows you to run any project right within your browser.
!!!

GitPod has a generous free tier of 50/hours per month for free.
> For our early testers, we also provide access to our GitPod organization which includes some credits and some pre-built environments to speedup the deployment time.

[!ref Check Infrahub in GitPod](https://gitpod.io/#/github.com/opsmill/infrahub)

## K8s with Helm charts

A first version of our K8S helm-chart is available in our repository.

[!ref Infrahub Helm Chart](https://github.com/opsmill/infrahub/tree/stable/helm)