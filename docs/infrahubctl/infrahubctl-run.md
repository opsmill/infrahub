# `infrahubctl run`

Execute a script.

**Usage**:

```console
infrahubctl run [OPTIONS] SCRIPT
```

**Arguments**:

* `SCRIPT`: [required]

**Options**:

* `--method TEXT`: [default: run]
* `--debug / --no-debug`: [default: no-debug]
* `--config-file TEXT`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--branch TEXT`: Branch on which to run the script.  [default: main]
* `--concurrent INTEGER`: Maximum number of requests to execute at the same time.  [env var: INFRAHUBCTL_CONCURRENT_EXECUTION; default: 4]
* `--timeout INTEGER`: Timeout in sec  [env var: INFRAHUBCTL_TIMEOUT; default: 60]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.
