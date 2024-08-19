# Infrahub Changelog

This is the changelog for Infrahub.
All notable changes to this project will be documented in this file.

Issue tracking is located in [Github](https://github.com/opsmill/infrahub/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub/tree/develop/infrahub/changelog/>.

<!-- towncrier release notes start -->

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
