# `infrahubctl branch`

Manage the branches in a remote Infrahub instance.

List, create, merge, rebase ..

**Usage**:

```console
$ infrahubctl branch [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `create`: Create a new branch.
* `delete`: Delete a branch.
* `diff`: Show the differences between a Branch and...
* `list`: List all existing branches.
* `merge`: Merge a Branch with main.
* `rebase`: Rebase a Branch with main.
* `validate`: Validate if a branch has some conflict and...

## `infrahubctl branch create`

Create a new branch.

**Usage**:

```console
$ infrahubctl branch create [OPTIONS] BRANCH_NAME [DESCRIPTION]
```

**Arguments**:

* `BRANCH_NAME`: [required]
* `[DESCRIPTION]`

**Options**:

* `--data-only / --no-data-only`: [default: data-only]
* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl branch delete`

Delete a branch.

**Usage**:

```console
$ infrahubctl branch delete [OPTIONS] BRANCH_NAME
```

**Arguments**:

* `BRANCH_NAME`: [required]

**Options**:

* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl branch diff`

Show the differences between a Branch and main.

**Usage**:

```console
$ infrahubctl branch diff [OPTIONS] BRANCH_NAME
```

**Arguments**:

* `BRANCH_NAME`: [required]

**Options**:

* `--from [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]`: Start Time used to calculate the Diff, Default: from the start of the branch
* `--to [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]`: End Time used to calculate the Diff, Default: now
* `--branch-only / --no-branch-only`: [default: branch-only]
* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl branch list`

List all existing branches.

**Usage**:

```console
$ infrahubctl branch list [OPTIONS]
```

**Options**:

* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl branch merge`

Merge a Branch with main.

**Usage**:

```console
$ infrahubctl branch merge [OPTIONS] BRANCH_NAME
```

**Arguments**:

* `BRANCH_NAME`: [required]

**Options**:

* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl branch rebase`

Rebase a Branch with main.

**Usage**:

```console
$ infrahubctl branch rebase [OPTIONS] BRANCH_NAME
```

**Arguments**:

* `BRANCH_NAME`: [required]

**Options**:

* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.

## `infrahubctl branch validate`

Validate if a branch has some conflict and is passing all the tests (NOT IMPLEMENTED YET).

**Usage**:

```console
$ infrahubctl branch validate [OPTIONS] BRANCH_NAME
```

**Arguments**:

* `BRANCH_NAME`: [required]

**Options**:

* `--config-file PATH`: [env var: INFRAHUBCTL_CONFIG; default: infrahubctl.toml]
* `--help`: Show this message and exit.
