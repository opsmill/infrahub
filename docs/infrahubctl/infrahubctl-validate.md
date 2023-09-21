# `infrahubctl validate`

Helper to validate the format of various files.

**Usage**:

```console
$ infrahubctl validate [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `graphql-query`: Validate the format of a GraphQL Query...
* `schema`: Validate the format of a schema file...

## `infrahubctl validate graphql-query`

Validate the format of a GraphQL Query stored locally by executing it on a remote GraphQL endpoint

**Usage**:

```console
$ infrahubctl validate graphql-query [OPTIONS] QUERY [VARIABLES]...
```

**Arguments**:

* `QUERY`: [required]
* `[VARIABLES]...`: Variables to pass along with the query. Format key=value key=value.

**Options**:

* `--debug / --no-debug`: Display more troubleshooting information.  [default: no-debug]
* `--branch TEXT`: Branch on which to validate the GraphQL Query.
* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl validate schema`

Validate the format of a schema file either in JSON or YAML

**Usage**:

```console
$ infrahubctl validate schema [OPTIONS] SCHEMA
```

**Arguments**:

* `SCHEMA`: [required]

**Options**:

* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.
