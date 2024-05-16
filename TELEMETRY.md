# Telemetry Data Collection

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
