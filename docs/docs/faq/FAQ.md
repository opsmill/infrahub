---
title: FAQ
---

# FAQ

<details>
<summary>

## Infrahub Product Status

</summary>

## What is the status of the Infrahub Project?

Infrahub offers best in class features for infrastructure automation such as:

- Customizable schemas
- Git-like branching and merging
- CI validations and approval process
- Object Profiles
- IPAM with IPv4 and IPv6 support
- Resource Managment
- User Defined Artifact Generation in CI
- User Defined Object Generation
- GUI, API, and SDK operations
- Data import with Infrahub Sync

Infrahub is still being actively developed with new features and functionalities coming on a regular basis. Check out our [roadmap](https://opsmill.atlassian.net/jira/discovery/share/views/7e5d4ab1-63d7-405e-b453-ad50cd9d5b71) to see where we aer going next!

### Can I deploy Infrahub in production?

Yes. Infrahub can be deployed in a production environment. If you are deploying a large production environment we recommend reacthing out to our customer success team at customer-success@opsmill.com to understand any specific requirments for your deployment.

</details>

<details>
<summary>

## Getting Involved with Infrahub

</summary>

## How can I submit a feature request?

We accept feature requests in our [GitHub](https://github.com/opsmill/infrahub/issues), in our [Discord](https://discord.gg/typQmqXan5)

## How can I get involved?

There are a few different ways to get involved with Infrahub:

1. As you use Infrahub, submit bugs and feature requests.
2. Reach out to OpsMill on [Discord](https://discord.gg/typQmqXan5) and set up a user feedback session to share your thoughts with us.
3. If you are a developer make a ticket on our [GitHub](https://github.com/opsmill/infrahub/issues) and send a PR our way to fix it.

</details>

<details>
<summary>

## Infrahub Telemetry

</summary>

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

</details>