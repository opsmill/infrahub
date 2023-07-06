# infrahubctl

`infrahubctl` is a command line utility designed to help with the day to day management of an Infrahub installation.
It's meant to run on any laptop or server and it communicates with a remote Infrahub server over the network.

`infrahubctl` can help you to
- Manage the branches in Infrahub : List, Create, Merge, Rebase, Delete
- Manage the schema and load new schema files into Infrahub
- Execute any Python script that requires access to the Python SDK
- Render a Jinja Template locally for troubleshooting
- Execute a GraphQL query store in a Git repository for troubleshooting
- Validate that input files conform with the format expected by Infrahub

## Configuration

`infrahubctl` requires a minimal set of configuration in order to connect to the right Infrahub server with the correct credentials. These settings can be provided either in a configuration file `infrahubctl.toml` or via environment variables.

### Environment Variables

| Name | Example value |
| -- | -- |
| `INFRAHUB_ADDRESS` | http://localhost:8000 |
| `INFRAHUB_API_TOKEN` | `06438eb2-8019-4776-878c-0941b1f1d1ec` |
| `INFRAHUB_DEFAULT_BRANCH` | main |

> the location of a configuration file can be also provided via environment variable : `INFRAHUBCTL_CONFIG`

### `infrahubctl.toml` file

```toml
# infrahubctl.toml
server_address="http://localhost:8000"
api_token="06438eb2-8019-4776-878c-0941b1f1d1ec"
```