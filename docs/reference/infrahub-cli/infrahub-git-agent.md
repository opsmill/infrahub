# `infrahub git-agent`

Control the Git Agent.

**Usage**:

```console
infrahub git-agent [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `start`: Start Infrahub Git Agent.

## `infrahub git-agent start`

Start Infrahub Git Agent.

**Usage**:

```console
infrahub git-agent start [OPTIONS] [PORT]
```

**Arguments**:

* `[PORT]`: Port used to expose a metrics endpoint  [env var: INFRAHUB_METRICS_PORT;default: 8000]

**Options**:

* `--debug / --no-debug`: Enable advanced logging and troubleshooting  [default: no-debug]
* `--config-file TEXT`: Location of the configuration file to use for Infrahub  [env var: INFRAHUB_CONFIG; default: infrahub.toml]
* `--help`: Show this message and exit.
