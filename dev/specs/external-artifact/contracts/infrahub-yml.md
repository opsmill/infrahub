# Contract: `external_transforms` in `.infrahub.yml`

```yaml
queries:
  - name: device_startup_config
    file_path: queries/device_startup_config.gql

external_transforms:
  - name: ansible-startup-config
    query: device_startup_config
    version: "1.5.0"
    description: Startup configuration rendered by the AWX job template "startup-config"
    timeout: 600

artifact_definitions:
  - name: startup-config
    artifact_name: startup-config
    parameters:
      device: name__value
    content_type: text/plain
    targets: edge-routers
    transformation: ansible-startup-config
```

| Key | Required | Rules |
|-----|----------|-------|
| `name` | yes | Unique across all transformations (`CoreTransformation.name` is unique). |
| `query` | yes | Name of a query declared in the same repository. |
| `version` | yes | Non-empty string, for example a release tag or a commit SHA of the template repository. Changing it changes the fingerprint of every artifact definition that uses the transformation. |
| `description` | no | |
| `timeout` | no | Seconds, default 600, minimum 1. This is the render deadline counted from the request. |

- `external_transforms` has no `watch` block and no file path, because the template is outside the repository.
- Duplicate names inside the section are refused, as for the other sections (`InfrahubRepositoryConfig.unique_items`).
- `infrahubctl render` and `infrahubctl transform` do not run external transformations.
