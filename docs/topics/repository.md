---
label: Repository
---
# External Git repository

An external Git repository will be loading into Infrahub, using `infrahubctl`. By default, `infrahubctl` is looking for a `.infrahub.yml` at the root of the repository.

## `.infrahub.yml` file

This configuration file will be use to link the different repository files to Infrahub type of objects:
- [RFile](/topics/transformation#rendered-file-jinja2-plugin)
- [Python Transformation](/topics/transformation#transformpython-python-plugin)
- [Artifact](/topics/artifact) Definition

It is also possible to declare [Schema](/topics/schema) to be [load via the git integration](/guide/schema)

!!!warning
Under construction
!!!
