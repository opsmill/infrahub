# `infrahubctl schema`

Manage the schema in a remote Infrahub instance.

**Usage**:

```console
infrahubctl schema [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `load`: Load a schema file into Infrahub.
* `migrate`: Migrate the schema to the latest version.

## `infrahubctl schema load`

Load a schema file into Infrahub.

**Usage**:

```console
infrahubctl schema load [OPTIONS] SCHEMAS...
```

**Arguments**:

* `SCHEMAS...`: [required]

**Options**:

* `--debug / --no-debug`: [default: no-debug]
* `--branch TEXT`: Branch on which to load the schema.  [default: main]
* `--config-file TEXT`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl schema migrate`

Migrate the schema to the latest version. (Not Implemented Yet)

**Usage**:

```console
infrahubctl schema migrate [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.
