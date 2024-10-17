# Infrahub Changelog

This is the changelog for Infrahub.
All notable changes to this project will be documented in this file.

Issue tracking is located in [Github](https://github.com/opsmill/infrahub/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub/tree/develop/infrahub/changelog/>.

<!-- towncrier release notes start -->

## [0.16.4](https://github.com/opsmill/infrahub/tree/v0.16.4) - 2024-10-17

### Fixed

- Fixed an issue on the UI where a new relationship was being added to the main branch instead of the current branch. ([#4598](https://github.com/opsmill/infrahub/issues/4598))


## [0.16.3](https://github.com/opsmill/infrahub/tree/v0.16.3) - 2024-10-10

### Removed

- Removed `infrahub.toml` configuration file from Docker builds.

### Fixed

- Save a diff in smaller pieces instead of all at once to prevent out-of-memory error. ([#4511](https://github.com/opsmill/infrahub/issues/4511))
- Fixes exception handling section in the Python SDK batch guide.

## [0.16.2](https://github.com/opsmill/infrahub/tree/v0.16.2) - 2024-10-01

### Fixed

- Loading a schema with an invalid order_by field raise a proper error. ([#4323](https://github.com/opsmill/infrahub/issues/4323))
- Updates internal logic to improve performance when generating a diff.

  BREAKING CHANGE: Diff data, including conflict selections, will be deleted. We recommend merging
  any outstanding proposed changes before upgrading to this version. ([#4438](https://github.com/opsmill/infrahub/issues/4438))
- Fix performance issue for GraphQL queries that only count nodes. ([#4454](https://github.com/opsmill/infrahub/issues/4454))
- Fix ability to construct HFID for upsert mutations where a number attribute is used. ([#4460](https://github.com/opsmill/infrahub/issues/4460))

## [0.16.1](https://github.com/opsmill/infrahub/tree/v0.16.1) - 2024-09-24

The largest change in this version is the movement of the Infrahub SDK into a
[separate repository](https://github.com/opsmill/infrahub-sdk-python) and package.

[Documentation for the SDK](https://docs.infrahub.app/python-sdk/) remains in the main Infrahub documentation at this time.

Developers may need to take the following steps to ensure their development environment has the proper SDK in place:

```shell
git checkout develop
git pull
rm -rf python_sdk
git submodule update --init
```

### Removed

- Removed Python SDK from Infrahub repository and migrated to dedicated repository at [https://github.com/opsmill/infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python).
  ([#4232](https://github.com/opsmill/infrahub/issues/4232))

### Added

- - In list views, always show relationships of type "Parent."
  - In the details view of an object, hide the "Parent" relationship if the parent is the current object itself.

  ([#3891](https://github.com/opsmill/infrahub/issues/3891))
- Add ability to construct HFIDs from payload for upsert mutations ([#4167](https://github.com/opsmill/infrahub/issues/4167))
- Add HFID to schema view in the frontend ([#4172](https://github.com/opsmill/infrahub/issues/4172))
- Update action buttons in details view and relationships views
  - in the details view, we can edit / delete the object and manage its groups
  - in the relationships views, we can add new relationships (it replaces the "+" button at the bottom)

  ([#4362](https://github.com/opsmill/infrahub/issues/4362))
- Prevent the form from being closed if there are unsaved changes. ([#4419](https://github.com/opsmill/infrahub/issues/4419))

### Fixed

- GraphQL results when querying nodes with `updated_at` named attributes will now return correct values instead of null/None ([#3730](https://github.com/opsmill/infrahub/issues/3730))
- Loading a schema with a SchemaNode referencing an incorrect menu placement now returns a proper HTTP 422 error ([#4089](https://github.com/opsmill/infrahub/issues/4089))
- GraphQL mutations to update a many relationship that is required on the peer will succeed or fail with the correct error ([#4124](https://github.com/opsmill/infrahub/issues/4124))
- Infer human-friendly ID for a schema if it includes a uniqueness constraint of a single attribute ([#4174](https://github.com/opsmill/infrahub/issues/4174))
- Account for uniqueness constraints of a single attribute when validating human-friendly ID ([#4181](https://github.com/opsmill/infrahub/issues/4181))
- Synchronize uniqueness_constraints and unique attributes during schema processing ([#4182](https://github.com/opsmill/infrahub/issues/4182))
- Ensure schema uniqueness_constraints are created if they are missing and human_friendly_id has been specified for the node ([#4186](https://github.com/opsmill/infrahub/issues/4186))
- Deleting a node that is linked to a mandatory relationship on a generic schema will now fail with an error message ([#4207](https://github.com/opsmill/infrahub/issues/4207))
- Fixed incorrect consumer timeout for RabbitMQ queue infrahub.rpcs

  If you are upgrading from a previous version of Infrahub and using the provided Docker Compose files you don't have to take any additional action. However if you are using your own setup for RabbitMQ you will need to manually delete the queue yourself.

  Swap the container name and credentials to RabbitMQ if they are different in your setup:

  ```bash
  docker exec -it infrahub-message-queue-1 rabbitmqadmin --username infrahub --password infrahub delete queue name=infrahub.rpcs
  ```

  After this step Infrahub and the Git agents need to be restarted, when doing so the correct queue will be recreated. ([#4308](https://github.com/opsmill/infrahub/issues/4308))
- Add documentation links for Generator Definition and Generator Instance pages to Generator topic ([#4316](https://github.com/opsmill/infrahub/issues/4316))
- Hierarchical node that don't have a parent or a children defined in the schema will properly enforce that constraint ([#4325](https://github.com/opsmill/infrahub/issues/4325))
- Properly raise errors instead of just logging them during repository import failures so that the "sync status" gets updated even if we've caught the errors. ([#4334](https://github.com/opsmill/infrahub/issues/4334))
- Display label composed of an attribute of type Enum will now render correctly ([#4382](https://github.com/opsmill/infrahub/issues/4382))
- Removed database index in Attribute Value to attribute larger than 8167 bytes ([#4399](https://github.com/opsmill/infrahub/issues/4399))
- Added cancel button in repository form ([#4402](https://github.com/opsmill/infrahub/issues/4402))
- Fixes the tasks pagination in the proposed changes tab ([#4434](https://github.com/opsmill/infrahub/issues/4434))

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
- Allow bare Git URL and automatically add `.git`. ([#4070](https://github.com/opsmill/infrahub/issues/4070))
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
