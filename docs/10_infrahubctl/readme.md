# infrahubctl

`infrahubctl` is a command line utility designed to help with the day to day management of an Infrahub installation.
It's meant to run on any laptop or server and it communicates with a remote server over the network.

infrahubctl can help you to
- Manage the branches in Infrahub : List, create, merge, rebase, delete
- Manage the schema and load new schema files into infrahub
- Visualize the differences between a given branch and main or between 2 timestamps
- Render a Jinja Template locally for troubleshooting
- Validate that input files conform with the format expected by Infrahub

## Configuration

`infrahubctl` requires a minimal set of configuration in order to connect to the right Infrahub server with the correct credentials. These settings can be provided either in a configuration file `infrahubctl.toml` or via environment variables

### Environment Variables

| Name | Example value |
| -- | -- |
| `INFRAHUB_ADDRESS` | http://localhost:8000 |

### `infrahubctl.toml` file

```toml
# infrahubctl.toml
server_address="http://localhost:8000"
```