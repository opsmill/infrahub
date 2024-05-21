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

<details>
<summary>

### Can I deploy Infrahub in production?

</summary>

Yes. Infrahub can be deployed in a production environment. If you are deploying a large production environment we recommend reacthing out to our customer success team at customer-success@opsmill.com to understand any specific requirments for your deployment.

</details>
</details>

<details>
<summary>

## Getting Involved with Infrahub

</summary>

<details>
<summary>

## How can I submit a feature request?

</summary>

We accept feature requests in our [GitHub](https://github.com/opsmill/infrahub/issues), in our [Discord](https://discord.gg/typQmqXan5)

</details>

<details>
<summary>

## How can I get involved?

</summary>

There are a few different ways to get involved with Infrahub:

- As you use Infrahub, submit bugs and feature requests.
- Reach out to OpsMill on [Discord](https://discord.gg/typQmqXan5) and set up a user feedback session to share your thoughts with us.
- If you are a developer make a ticket on our [GitHub](https://github.com/opsmill/infrahub/issues) and send a PR our way to fix it.

</details>
</details>

<details>
<summary>

## Infrahub Telemetry

</summary>

## Does Infrahub Collect Telemetry?

Infrahub collects limited telemetry for the purpose of product analytics.

<details>
<summary>

### Telemetry Items Collected

</summary>

- Up/Down status of services
- Number of Nodes
- Number of Objects Created
- Count of Branches Created
- Count of Branches not yet merged
- Number of Resource Pools
- Obfuscated Schema Summary
- Infrahub Version
- Number of GIT Repositories
- Number of workers
- Number of generators
- Number of artifact definitions
- Number of times artifacts are being generated
- Number of transformation
- Number of groups
- Number of profiles
- Number of webhooks
- Number of times webhooks fired

</details>

<details>
<summary>

### Controlling Telemetry

</summary>

To disable telemetry you can set INFRAHUB_TELEMETRY_OPTOUT prior to the build step for Infrahub.
    export INFRAHUB_TELEMETRY_OPTOUT=true

</details>
</details>