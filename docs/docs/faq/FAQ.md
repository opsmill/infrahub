---
title: FAQ
---

# FAQ

## What is the status of the Infrahub Project?

Infrahub is currently in Open Beta. Many functionalities are still being actively developed or iterated upon.

## How can I submit a feature request?

We accept feature requests in our [GitHub](https://github.com/opsmill/infrahub/issues), in our [Discord](https://discord.gg/typQmqXan5)

## How can I get involved?

There are a few different ways to get involved with Infrahub:

1. As you use Infrahub, submit bugs and feature requests.
2. Reach out to OpsMill on [Discord](https://discord.gg/typQmqXan5) and set up a user feedback session to share your thoughts with us.
3. If you are a developer make a ticket on our [GitHub](https://github.com/opsmill/infrahub/issues) and send a PR our way to fix it.

## Does Infrahub Collect Telemetry?

Infrahub collects limited telemetry for the purpose of product analytics.

### Telemetry Items Collected

1. Up/Down status of services
2. Number of Nodes
3. Number of Objects Created
4. Count of Branches Created
5. Count of Branches not yet merged
6. Number of Resource Pools
7. Obfuscated Schema Summary
8. Infrahub Version
9. Number of GIT Repositories
10. Number of workers
11. Number of generators
12. Number of artifact definitions
13. Number of times artifacts are being generated
14. Number of transformation
15. Number of groups
16. Number of profiles
17. Number of webhooks
18. Number of times webhooks fired

### Controlling Telemetry

To disable telemetry you can set INFRAHUB_TELEMETRY_OPTOUT prior to the build step for Infrahub.
    export INFRAHUB_TELEMETRY_OPTOUT=true