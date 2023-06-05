
# Developer Guide

## Backend / Python

### Code Linting

- **yamllint**
- **Black**
- **ruff**
- **pylint**
- (soon) **mypy**
- (soon) **pydocstyle**

`invoke tests` will run all the linter at once to quickly validate if all files have the right format and are compliant with the internal coding guidelines.

To help format the code correctly, the project is also recommending:
- **autoflake** to automatically remove all unused variables and all unused import
- **isort** to automatically sort all imports

> `invoke format` will run Black, autoflake and isort together to ensure all files are as close as possible to the expected format.


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
```


## FrontEnd

### Code Linting

### Run tests


## Developer Environment

### VS Code Extensions

- Excalidraw: https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor
- Jinja: https://marketplace.visualstudio.com/items?itemName=wholroyd.jinja
- Pylance: https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance
- Trailing Space: https://marketplace.visualstudio.com/items?itemName=shardulm94.trailing-spaces
- Better Toml: https://marketplace.visualstudio.com/items?itemName=bungcip.better-toml
- GraphQL: https://marketplace.visualstudio.com/items?itemName=GraphQL.vscode-graphql
- Ruff: https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff
- Black Formatter: https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter
- isort: https://marketplace.visualstudio.com/items?itemName=ms-python.isort

Sample .vscode/settings.json

```json
{
    "black-formatter.importStrategy": "fromEnvironment",
    "python.formatting.provider": "none",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": true
        }
    },
    "python.analysis.typeCheckingMode": "basic",
    "python.testing.pytestArgs": [
        "backend"
    ],
    "python.testing.unittestEnabled": false,
    "python.testing.pytestEnabled": true
}
```