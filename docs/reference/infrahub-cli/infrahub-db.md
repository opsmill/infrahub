# `infrahub db`

Manage the graph in the database.

**Usage**:

```console
$ infrahub db [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `init`: Erase the content of the database and...
* `load-test-data`: Load test data into the database from the...

## `infrahub db init`

Erase the content of the database and initialize it with the core schema.

**Usage**:

```console
$ infrahub db init [OPTIONS]
```

**Options**:

* `--config-file TEXT`: Location of the configuration file to use for Infrahub  [env var: INFRAHUB_CONFIG; default: infrahub.toml]
* `--help`: Show this message and exit.

## `infrahub db load-test-data`

Load test data into the database from the `test_data` directory.

**Usage**:

```console
$ infrahub db load-test-data [OPTIONS]
```

**Options**:

* `--config-file TEXT`: Location of the configuration file to use for Infrahub  [env var: INFRAHUB_CONFIG; default: infrahub.toml]
* `--dataset TEXT`: [default: dataset01]
* `--help`: Show this message and exit.
