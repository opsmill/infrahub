# `infrahub git-agent`

Control the Git Agent.

**Usage**:

```console
$ infrahub git-agent [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `start`

## `infrahub git-agent start`

**Usage**:

```console
$ infrahub git-agent start [OPTIONS] [CONFIG_FILE] [PORT]
```

**Arguments**:

* `[CONFIG_FILE]`: [env var: INFRAHUB_CONFIG;default: infrahub.toml]
* `[PORT]`: Port used to expose a metrics endpoint  [default: 8000]

**Options**:

* `--interval INTEGER`: [default: 10]
* `--debug / --no-debug`: [default: no-debug]
* `--help`: Show this message and exit.
