


# Introduction

Infrahub is composed of multiple components, the backend is mostly written in Python and the frontend in React.

The main dependencies are:
- Neo4j 5.x
- RabbitMQ
- `Poetry` to install the python packages
- `npm` to install the Javascript packages

## Docker Compose

Currently, the recommended way to run Infrahub is to use the docker-compose project included with the project combined with the helper commands defined in `invoke`

```
invoke demo.build demo.init demo.start
```

[!ref Check the documentation of the demo environment for more information](../20_knowledge_base/80_local_demo_environment.md)

## GitPod

The project is also pre-configured to run in GitPod

!!!
GitPod provides a Cloud Development Environment that makes it very easy to run any project right within your browser.
!!!

GitPod has a generous free tier of 50/hours per month for free.  
> For our early testers, we also provide access to our GitPod organization which includes some credits and some pre-built environments to speedup the deployment time.

[!ref Check Infrahub in GitPod](https://gitpod.io/#/github.com/opsmill/infrahub)