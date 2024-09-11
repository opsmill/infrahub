# Infrahub Changelog

This is the changelog for Infrahub.
All notable changes to this project will be documented in this file.

Issue tracking is located in [Github](https://github.com/opsmill/infrahub/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub/tree/develop/infrahub/changelog/>.

<!-- towncrier release notes start -->

## [0.16.0](https://github.com/opsmill/infrahub/tree/v0.16.0) - 2024-09-11

### Removed

- Removed isolated branch information from schema topic in the documentation. ([#3968](https://github.com/opsmill/infrahub/issues/3968))

### Added

- Allow adding multiple profiles to an object in the UI. ([#3061](https://github.com/opsmill/infrahub/issues/3061))
- Added "disabled" attribute to accounts to allow more granular user management. ([#3505](https://github.com/opsmill/infrahub/issues/3505))
- Added capabilities to manage API tokens in the Infrahub UI. ([#3527](https://github.com/opsmill/infrahub/issues/3527))
- Added filtering and search to IPAM view. ([#3740](https://github.com/opsmill/infrahub/issues/3740))
- Add number of prefixes to IPAM tree view. ([#3741](https://github.com/opsmill/infrahub/issues/3741))
- Allow navigation to related node in list view. ([#3889](https://github.com/opsmill/infrahub/issues/3889))
- Add support to search a node by human friendly ID within a GraphQL query. ([#3908](https://github.com/opsmill/infrahub/issues/3908))
- Added DB migrations for objects changed to Generic type in 0.16. ([#3915](https://github.com/opsmill/infrahub/issues/3915))
- Add clickable items in the Proposed Change list view. ([#3990](https://github.com/opsmill/infrahub/issues/3990))
- Added the ability to filter out Infrahub internal groups. ([#4027](https://github.com/opsmill/infrahub/issues/4027))
- Add action button to Repository objects. ([#4066](https://github.com/opsmill/infrahub/issues/4066))
- Added documentation for creating custom Infrahub Docker images. ([#4077](https://github.com/opsmill/infrahub/issues/4077))
- Add support for numbers bigger or smaller than signed integers. ([#4179](https://github.com/opsmill/infrahub/issues/4179))

### Changed

- Move GraphQL queries to .infrahub.yml for Repository imports. ([#1938](https://github.com/opsmill/infrahub/issues/1938))
- Improve UI of Git repository form. ([#3893](https://github.com/opsmill/infrahub/issues/3893))
- Consistency improvements in Repository interactions. ([#4068](https://github.com/opsmill/infrahub/issues/4068))
- Enhancements to Repository status reporting. ([#4069](https://github.com/opsmill/infrahub/issues/4069))
- Simplified the Repository view to only show crucial information. ([#4071](https://github.com/opsmill/infrahub/issues/4071))
- Increased visibility during Git sync. ([#4072](https://github.com/opsmill/infrahub/issues/4072))

### Fixed

- Add ability to import repositories with default branch other than 'main'. ([#3435](https://github.com/opsmill/infrahub/issues/3435))
- SchemasLoadAPI should not inherited from SchemaRoot but from BaseModel. ([#3821](https://github.com/opsmill/infrahub/issues/3821))
- Resolve inconsistencies when loading same schema twice. ([#3892](https://github.com/opsmill/infrahub/issues/3892))
- HFID of a node is not properly set by `prefetch_relationship` in Python SDK. ([#3900](https://github.com/opsmill/infrahub/issues/3900))
- Comment input is not cleared upon submission of Proposed Change form. ([#3942](https://github.com/opsmill/infrahub/issues/3942))
- Can not assign Profile when editing Node in the web UI. ([#3999](https://github.com/opsmill/infrahub/issues/3999))
- Allow users to add a new generic to an existing node. ([#4051](https://github.com/opsmill/infrahub/issues/4051))
- Allow users to run artifacts and generators on nodes without name attribute ([#4062](https://github.com/opsmill/infrahub/issues/4062))
- Allow bare Git url and automatically add `.git`. ([#4070](https://github.com/opsmill/infrahub/issues/4070))
- Schema diff view not functioning in branch detail page. ([#4093](https://github.com/opsmill/infrahub/issues/4093))
- Removed erroneous approval button on Diff view. ([#4094](https://github.com/opsmill/infrahub/issues/4094))
- Edit node form displays empty input field for mandatory relationship of cardinality many. ([#4102](https://github.com/opsmill/infrahub/issues/4102))
- GraphQL query does not appear on Detail page. ([#4105](https://github.com/opsmill/infrahub/issues/4105))
- Do not allow '/' character in repository name to avoid sync failure. ([#4120](https://github.com/opsmill/infrahub/issues/4120))
- Can't close a comment thread on an Artifact. ([#4189](https://github.com/opsmill/infrahub/issues/4189))

## [0.15.3](https://github.com/opsmill/infrahub/tree/v0.15.3) - 2024-08-13

### Added

- Add usage of Towncrier to generate Changelog as part of the release process.
  For detailed information, see the [Documentation](https://docs.infrahub.app/development/changelog). ([#4023](https://github.com/opsmill/infrahub/issues/4023))
- Serve Swagger & Redoc files locally so that the REST-API docs work offline or when isolated from the internet. ([#4063](https://github.com/opsmill/infrahub/issues/4063))

### Fixed

- Fix attribute uniqueness check that was incorrectly running against schema nodes, ([#3986](https://github.com/opsmill/infrahub/issues/3986))
- Provide better information when available during schema conflicts in the pipeline. ([#3987](https://github.com/opsmill/infrahub/issues/3987))
- Fix schema sync issue between worker nodes. ([#3994](https://github.com/opsmill/infrahub/issues/3994))
- Updates the profile type select when creating a profile, to display more relevant information about the related nodes. ([#4001](https://github.com/opsmill/infrahub/issues/4001))
- Fix logic that prevented existing inherited attribute / relationships from being updated. ([#4004](https://github.com/opsmill/infrahub/issues/4004))
- Fix attribute uniqueness validator to not run in isolated mode. ([#4025](https://github.com/opsmill/infrahub/issues/4025))
- Update getting-started/branches referencing the wrong org from previous step.
  Update getting-started/resource-manager referencing the wrong button.
  Regenerate the screenshots for the tutorial. ([#4035](https://github.com/opsmill/infrahub/issues/4035))
- Fix object creation for schema node using enum attribute in uniqueness constraint groups. ([#4054](https://github.com/opsmill/infrahub/issues/4054))
