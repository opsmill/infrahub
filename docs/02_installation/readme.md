


# Introduction

Infrahub is composed of multiple components, the backend is mostly written in Python and the frontend in React.

The main components are:
- **A Frontend** written in react
- An **API Server** written in Python with FastAPI
- A **Git agent** to manage the interaction with external Git repositories
- A **Graph Database** based on `Neo4j` 5.x or `memgraph`
- A **Message Bus** based on `RabbitMQ`

## Docker Compose

Currently, the recommended way to run Infrahub is to use the docker-compose project included with the project combined with the helper commands defined in `invoke`

The pre-requisites for this type of deployment are to have:
- [Invoke](https://www.pyinvoke.org) (version 2 minimum) and Toml
- [Docker](https://docs.docker.com/engine/install/) (version 24.x minimum)



+++ Mac OS

### Invoke

On Mac OS Python is installed by default so you should be able to install `invoke` directly. 
Invoke works best when you install it in the main Python but you can also install it in a virtual environment if you prefer.

```
pip install invoke toml
```

### Docker

For Docker, you can download Docker Desktop directly from Docker's website with the instructions https://docs.docker.com/desktop/install/mac-install/

+++ Windows

The current recommendation for Windows is to install a Linux VM via WSL2 and follow the installation guide for Ubuntu.

!!!
The native support on Windows is currently under investigation and is being tracked in the [issue 794](https://github.com/opsmill/infrahub/issues/794).  
Please add a comment to the issue if this is something that would be useful to you.
!!!

+++ Ubuntu

!!!warning
On Ubuntu, depending on which distribution you're running there is a good chance your version of Docker might be outdated.
!!!

### Invoke

Invoke is a Python package that is usually installed with `pip install invoke toml`.  
If Python is not already installed on your system you'll need to install it first with `sudo apt install python3-pip`

### Docker


You can check if docker is installed and which version of docker is installed with `docker --version`  
The version should be at least `24.x`. if the version is `20.x` it's recommended to upgrade.

[This tutorial (for Ubuntu 22.04) explains how to install the latest version of docker on Ubuntu](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-22-04)

+++ Other

The deployment should work on any systems that can run a modern version of Docker and Python. 

Please reach out if you need some help and feel free to send a PR with the installation instructions for your platform.

+++

Once docker desktop and invoke are properly installed you can build start Infrahub with the following command
```
invoke demo.build demo.init demo.start demo.load-infra-schema demo.load-infra-data
```

[!ref Check the documentation of the demo environment for more information](../20_knowledge_base/local_demo_environment.md)

## GitPod

The project is also pre-configured to run in GitPod

!!!
GitPod provides a Cloud Development Environment that makes it very easy to run any project right within your browser.
!!!

GitPod has a generous free tier of 50/hours per month for free.
> For our early testers, we also provide access to our GitPod organization which includes some credits and some pre-built environments to speedup the deployment time.

[!ref Check Infrahub in GitPod](https://gitpod.io/#/github.com/opsmill/infrahub)

## K8s with Helm Chart

The support for K8s is not yet available but we are actively tracking this effort in our short/mid-term roadmap
https://github.com/opsmill/infrahub/issues/506
Please reach out and let us know you are interested in this feature, it's always helpful to prioritize what the team needs to focus on.
