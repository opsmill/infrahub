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

* `schema`: Validate the format of a schema file...

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
