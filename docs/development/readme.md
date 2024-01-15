# Developer guide

## Backend / Python

### Code linting

- **yamllint**
- **ruff**
- **pylint**
- (soon) **mypy**
- (soon) **pydocstyle**

`invoke tests` will run all the linter at once to quickly validate if all files have the right format and are compliant with the internal coding guidelines.

To help format the code correctly, the project is also recommending:

- **autoflake** to automatically remove all unused variables and all unused import

> `invoke format` will run Ruff and autoflake together to ensure all files are as close as possible to the expected format.

### Run tests

```shell
invoke dev-start
infrahub test unit
infrahub test integration tests/integration/client/
infrahub test integration tests/integration/user_workflows/
infrahub test client
infrahub test ctl
```

or

```shell
infrahub test unit <path>