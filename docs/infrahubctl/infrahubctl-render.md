# `infrahubctl render`

Render a local Jinja Template (RFile) for debugging purpose.

**Usage**:

```console
$ infrahubctl render [OPTIONS] RFILE [VARIABLES]...
```

**Arguments**:

* `RFILE`: [required]
* `[VARIABLES]...`: Variables to pass along with the query. Format key=value key=value.

**Options**:

* `--branch TEXT`: Branch on which to rendre the RFile.
* `--debug / --no-debug`: [default: no-debug]
* `--config-file TEXT`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.
