# infrahubctl

`infrahubctl` is a command line utility designed to help with the day to day management of an Infrahub server.
It's meant to run on any laptop of server and it communicate with a remote server over the network.

infrahubctl can help you to
- Manage the branches in Infrahub : List, create, merge, rebase ..
- Manage the schema and load some new schema file into infrahub
- Visualize the differences between a given branch and main or between 2 timestamps
- Render a Jinja Template locally for troubleshooting
- Validate that some input files are conform with the format expected by Infrahub

## Configuration

`infrahubctl` requires a mininal set of configuration in order to connect to the right Infrahub server with the right credential. These settings can be provided either in a configuration file `infrahubctl.toml` or via environment variables

### Environment Variables

| Name | Example value |
| -- | -- |
| `INFRAHUB_ADDRESS` | http://localhost:8000 |

### `infrahubctl.toml` file

```toml
# infrahubctl.toml
server_address="http://localhost:8000"
```