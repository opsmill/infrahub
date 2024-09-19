# Infrahub SDK Changelog

This is the changelog for the Infrahub SDK.
All notable changes to this project will be documented in this file.

Issue tracking is located in [Github](https://github.com/opsmill/infrahub/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub/tree/develop/infrahub/python_sdk/changelog/>.

<!-- towncrier release notes start -->

## [0.13.0](https://github.com/opsmill/infrahub/tree/v0.13.0) - 2024-09-12

### Added

- Add support to search a node by human friendly ID using client's `get` method ([#3908](https://github.com/opsmill/infrahub/issues/3908))
- Add support for Number resource pool

### Changed

- Fix `infrahubctl` not displaying error message under certain conditions

### Fixed

- Fix fetching relationship attributes when relationship inherits from a generic ([#3900](https://github.com/opsmill/infrahub/issues/3900))
- Fix the retrieving on schema and nodes on the right branch ([#4056](https://github.com/opsmill/infrahub/issues/4056))
