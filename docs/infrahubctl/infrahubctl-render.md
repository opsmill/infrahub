# `infrahubctl render`

Render a local Jinja2 Transform for debugging purpose.

**Usage**:

```console
$ infrahubctl render [OPTIONS] TRANSFORM_NAME [VARIABLES]...
```

**Arguments**:

* `TRANSFORM_NAME`: [required]
* `[VARIABLES]...`: Variables to pass along with the query. Format key=value key=value.

**Options**:

* `--branch TEXT`: Branch on which to render the transform.
* `--debug / --no-debug`: [default: no-debug]
* `--config-file TEXT`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.
