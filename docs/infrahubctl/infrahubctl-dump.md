# `infrahubctl dump`

Export node(s).

**Usage**:

```console
infrahubctl dump [OPTIONS]
```

**Options**:

* `--namespace TEXT`: Namespace(s) to export
* `--directory PATH`: Directory path to store export.  [default: (dynamic)]
* `--quiet / --no-quiet`: No console output  [default: no-quiet]
* `--config-file TEXT`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--branch TEXT`: Branch from which to export  [default: main]
* `--concurrent INTEGER`: Maximum number of requests to execute at the same time.  [env var: INFRAHUBCTL_CONCURRENT_EXECUTION; default: 4]
* `--timeout INTEGER`: Timeout in sec  [env var: INFRAHUBCTL_TIMEOUT; default: 60]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.
