# Infrahub changelog

This is the changelog for Infrahub.
All notable changes to this project will be documented in this file.

Issue tracking is located in [GitHub](https://github.com/opsmill/infrahub/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub/tree/develop/infrahub/changelog/>.

<!-- towncrier release notes start -->

## [Infrahub - v1.2.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.7) - 2025-04-28

### Security

- Update the `h11` package to 0.16.0.

### Fixed

- Mutating a backend node with extra attributes now logs an error instead of raising an error. It also fixes an issue
  preventing a corrupted node mutation. ([#6349](https://github.com/opsmill/infrahub/issues/6349))
- Improved the performance of computed attributes when updating a large number of objects at once. Replaced client.filter call in Jinja2 based computed attributes. ([#6351](https://github.com/opsmill/infrahub/issues/6351))
- Improved the IPAM allocation performance by leveraging database indexes (+10% improvement).

### Housekeeping

- Updated the Python `certifi` package to 2025.1.31.
- Updated Infrahub SDK to version 1.11.1.

## [Infrahub - v1.2.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.6) - 2025-04-18

### Added

- Added generics to node selection in number pool form.
- Enabled node select in the webhook form to quickly choose the node kind.

### Changed

- Raised a more accurate error when trying to lookup a node by HFID, specifically when the schema does not have an HFID or the number of elements does not match.

### Fixed

- Cleared GraphQL schema manager cache when deleting branches to release memory. ([#6021](https://github.com/opsmill/infrahub/issues/6021))
- Added attributes and relationships to generic templates to ensure proper GraphQL schema generation. ([#6287](https://github.com/opsmill/infrahub/issues/6287))
- Fixed node lookup by its HFID with a generic template kind. ([#6301](https://github.com/opsmill/infrahub/issues/6301))
- Disabled option creation for restricted namespaces in dropdown and enum.

## [Infrahub - v1.2.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.5) - 2025-04-11

### Added

- Added support for computed attributes on generics. ([#5736](https://github.com/opsmill/infrahub/issues/5736))
- Added new `infrahub db selected-export` command to run an anonymized export of selected object that includes no actual data. ([#6248](https://github.com/opsmill/infrahub/issues/6248))
- Added a migration to correctly set children of 0.0.0.0/0 and ::/0 IP prefixes if they exist.
- Updated the component relationship form to quickly create a new object and associate it to the current node.

### Changed

- Allowed using a generic in a number pool to group number allocation for all nodes inheriting from a given generic. ([#6080](https://github.com/opsmill/infrahub/issues/6080))
- Allowed specifying an empty string for optional text schema attributes in order to remove existing values.

### Fixed

- Refactored management of diff summary within pipelines so that they are stored in cache instead of a database. On a proposed change with large branches the size could be significant which lead to longer pipeline runs and slower lookup of tasks after they had run. ([#5866](https://github.com/opsmill/infrahub/issues/5866))
- Fixed the ability to override default timeout for Python transform and checks. ([#6267](https://github.com/opsmill/infrahub/issues/6267))
- Fixed a vertical scrolling issue in hierarchical node detailed view. ([#6269](https://github.com/opsmill/infrahub/issues/6269))
- Fixed a horizontal scrolling issue in tabs. ([#6272](https://github.com/opsmill/infrahub/issues/6272))
- Fixed the upsert operation when updating relationships with cardinality `one` or `many` having min/max count constraints.

## [Infrahub - v1.2.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.4) - 2025-04-04

### Fixed

- Fixed the migration to remove an attribute from a schema to correctly ignore overridden attributes from a generic schema. ([#6073](https://github.com/opsmill/infrahub/issues/6073))
- Fixed an issue where HFID and uniqueness constraints for component templates would end up having duplicate elements after loading several schemas.
- Fixed an issue where optional unique attributes having a NULL value could be duplicated.
  Upgrading Infrahub to a version containing this fix will perform a check identifying such duplicates.
  If some duplicates are found, data or schema should be fixed in order to complete the upgrade:
  - Either the uniqueness constraint on corresponding attributes should be removed within schema.
  - Or duplicated unique attributes values should be modified.
- Properly clear references to old branches and schema objects from the registry when deleting branches.
- Restricted event.related payload for CoreGraphQLQueryGroup events.

## [Infrahub - v1.2.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.3) - 2025-03-31

### Added

- Added support for Jinja2 filters from Netutils. ([#5899](https://github.com/opsmill/infrahub/issues/5899))

### Fixed

- Fixed the menu upgrade when Non-Builtin items are attached to a Builtin menu item. ([#6182](https://github.com/opsmill/infrahub/issues/6182))
- Added a migration to backfill hierarchy data missing from the default branch after a branch is merged and then deleted. The root cause of the missing data has already been fixed. ([#6019](https://github.com/opsmill/infrahub/issues/6019))
- Fixed a broken hierarchy when renaming a kind participating to a hierarchy. ([#6051](https://github.com/opsmill/infrahub/issues/6051))
- Fixed the schema migration validator to allow renaming the kind of a generic. ([#6060](https://github.com/opsmill/infrahub/issues/6060))
- Fixed an error in IPAM reconciliation logic to correctly assign 0.0.0.0/0 as a parent prefix. ([#6172](https://github.com/opsmill/infrahub/issues/6172))
- Ensured that node level migrations are not executed on a generic.
- Fixed updating a node through Upsert when payload contains existing unique attributes not part of HFID.

## [Infrahub - v1.2.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.2) - 2025-03-28

### Infrahub Enterprise

- Fixed the `infrahub upgrade` command not working properly in Infrahub Enterprise.

### Fixed

- Fixed generic schema updates to correctly propagate an updated order_weight to a downstream attribute or relationship on an inheriting schema. ([#5684](https://github.com/opsmill/infrahub/issues/5684))
- Fixed operational status of repositories remaining to "Unknown" even after a synchronization. ([#5755](https://github.com/opsmill/infrahub/issues/5755))
- Fixed an issue that could cause the display label to not appear for nodes that have had their kind updated.

## [Infrahub - v1.2.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.1) - 2025-03-26

### Added

- Added relationships changes details in the activities.
- Added an `INFRAHUB_SCHEMA_STRICT_MODE` environment variable. When set to `False`, `human_friendly_id` schema fields should not necessarily target a unique combination of peer attributes. Default is `True`.

### Changed

- Modified the event filters for mandatory computed attributes to not include the `infrahub.node.created` event as the computed attribute will be rendered on node creation regardless. This change will avoid extra processing in the background workers. ([#6105](https://github.com/opsmill/infrahub/issues/6105))
- Improved the event trigger filters for Transform based computed attributes to limit the number of tasks being triggered when updating impacted attributes. This will increase the overall performance when an update is triggered. ([#6113](https://github.com/opsmill/infrahub/issues/6113))
- Used the new `schema_hash` parameter from client.schema.all() in the SDK to only selectively refresh the branch schema cache if the current hash differs from the one in the cache. This will provide a speedup for Jinja2 based computed attributes. ([#6133](https://github.com/opsmill/infrahub/issues/6133))
- Improved performance for the upsert GraphQL Mutation.
- Rename command `demo.migrate` to `demo.upgrade`

### Fixed

- Prevented the editing of metadata on a read only attribute in the UI. ([#5558](https://github.com/opsmill/infrahub/issues/5558))
- Fixed an issue that prevents attributes and relationships on schema which inherit from a generic from receiving updates to the generic-level attributes or relationships. ([#5793](https://github.com/opsmill/infrahub/issues/5793))
- Fixed a broken hierarchy when renaming a kind participating to a hierarchy. ([#6051](https://github.com/opsmill/infrahub/issues/6051))
- Fixed the merge button state depending on ongoing merge tasks. ([#6059](https://github.com/opsmill/infrahub/issues/6059))
- Fixed the schema migration validator to allow renaming the kind of a generic. ([#6060](https://github.com/opsmill/infrahub/issues/6060))
- Ensured that if a node has a custom view, users should be taken there instead of the generic view.
- Fixed addresses having multiple prefixes after loading prefixes concurrently.
- Fixed the creation of related nodes when instantiating a template in a branch other than the default one.
- Updated the version of Internal graph to ensure that 1.2 migrations are properly applied.

## [Infrahub - v1.2.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.0) - 2025-03-19

### Added

- Added Containerlab to the GitHub Codespace base image. ([#458](https://github.com/opsmill/infrahub/issues/458))
- We have completely redesigned the object tables to improve usability, performance, and clarity:

  - Display Improvements:
    - Attributes and relationships are now clearly differentiated in the table
    - HFID is displayed when available

  - Performance Enhancements:
    - Infinite scroll replaces pagination for smoother navigation
    - Query performance improved for faster node list loading

  - Filtering Enhancements:
    - Filter specific columns directly by clicking the column header
    - New conditional filters: *contains*, *is empty*, *is not empty*
    - **Note:** Filtering is not yet available in relationship tables

  - New action menu on each row; edit or delete a node without opening the detail page
  - And more coming soon!

  ([#3456](https://github.com/opsmill/infrahub/issues/3456))
- You can now manually trigger a Generator Instance or Generation Definition run from the UI. ([#5354](https://github.com/opsmill/infrahub/issues/5354))
- Added validation to the UI for `min_count` and `max_count` in relationships fields. ([#5661](https://github.com/opsmill/infrahub/issues/5661))
- Added a new feature to create object templates when setting `generate_template: true` in the schema on a node.
- Added activities logs into the node details view.
- Added icon support to sub-menu items in the sidebar.
- Improved Infrahub app layout for a cleaner look. Made the top menu more compact.
- On object creation, you can now specify a list of groups to add the object to.
- We updated the global UI layout for better balance, alignment, and to prepare for future enhancements.

### Changed

- Replaced `PrefixPool` with `netaddr.IPSet`. ([#3547](https://github.com/opsmill/infrahub/issues/3547))
- Modified the query analyzer to not list all potential meta data models when only querying for "source" or "owner" ID. The full models will still show up if a fragment is used under the meta data properties. This change makes it easier to setup fine grained permissions and also speeds up the permission lookup as it doesn't require as many checks. ([#4644](https://github.com/opsmill/infrahub/issues/4644))
- Improved typing of GraphQL schema by defining list as non-nullable and ensure that top level item are mandatory.
- Made object list retrieval faster with an optimized query.
- Reorganized builtin/default menu to provide a better user experience. The "Unified Storage" and "Change Control" sections have been deprecated, and their contents moved to either Object Management or Integrations to be more aligned with the purpose of each page.
- Updated Infrahub account tokens view:

  - Redesigned for a faster, cleaner experience.
  - Improved clarity and formatting of expiration dates.
  - Resolved an issue where expiration data was not being sent to the API.

### Fixed

- Fixed a bug where deleting an object from the details view keeps you on your current branch instead of redirecting to the main branch. ([#5232](https://github.com/opsmill/infrahub/issues/5232))
- Fixed an event error in event state after merging a proposed change, they were incorrectly set as "merging" instead of "merged". ([#5600](https://github.com/opsmill/infrahub/issues/5600))
- Fixed an issue where the pool selection was not displayed correctly when eligible in a hierarchical relationship field. ([#5888](https://github.com/opsmill/infrahub/issues/5888))
- Default prefix type in IP Prefix Pool form can now be selected from a dropdown. ([#5889](https://github.com/opsmill/infrahub/issues/5889))
- Fixed incorrect toast messages for IP address pool creation, updates, and errors. ([#5908](https://github.com/opsmill/infrahub/issues/5908))
- Resolved an issue where Generic/Component Relationships couldn’t be added or updated in IPAM views. ([#5924](https://github.com/opsmill/infrahub/issues/5924))
- Infrahub will now correctly display all relationships in IPAM summary views ([#5925](https://github.com/opsmill/infrahub/issues/5925))
- Fixed an issue where list attribute could not be cleared using UI edit form. ([#5934](https://github.com/opsmill/infrahub/issues/5934))

### Housekeeping

- Activated `ruff` B rules. ([#2193](https://github.com/opsmill/infrahub/issues/2193))
- Activated `ruff` C4 rule. ([#2194](https://github.com/opsmill/infrahub/issues/2194))
- Added a basic integration test for the HTTP service adapter. ([#5553](https://github.com/opsmill/infrahub/issues/5553))

## [Infrahub - v1.1.9](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.9) - 2025-03-16

### Added

- Improved the performance of the GraphQL cardinality-many relationship resolver by batching database calls together.

### Fixed

- Fixed a bug in the logic to merge a branch or proposed change which deleted hierarchical node information. Added a migration to correct the issue on existing databases. ([#6019](https://github.com/opsmill/infrahub/issues/6019))
- Fixed a bug in one of the cypher queries to get related nodes that could cause a crash when trying to retrieve a schema from the database if that schema was merged in from a branch.

## [Infrahub - v1.1.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.8) - 2025-03-07

### Changed

- Improved the performance of the cypher query that saves a diff in the database.
- Updated the DiffUpdate mutation to return the ID of the task when `wait_until_completion` is False. Also, the argument `wait_for_completion` under the data section is deprecated and it has been replaced with `wait_until_completion` at the root of the mutation instead to align with the format of the other mutations.

### Fixed

- Fixed an error in the query to count the number of peers for a given cardinality-many relationship. Existing logic could have resulted in the count being multiplied by a power of 2 if changes were made to the relationship during a merge.
- Fixed the HFID format in the mutations `IPAddressPoolGetResource` and `IPPrefixPoolGetResource`.
- Reduced the number of database queries we run when checking a uniqueness constraint during a node update or create mutation. Specifically in the instance that node uses a schema which inherits from a generic schema and the node schema's uniqueness constraints are contained within the generic schema's uniqueness constraints.
- Removed duplicated edges that could have been added to the database during concurrent updates.

## [Infrahub - v1.1.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.7) - 2025-02-18

### Added

- Data diffs are loaded in sequential batches for faster performance with large changes.
- The diff tree and diff list can now be scrolled independently.

### Changed

- Modified node mutation events to not send metadata properties as part of the mutation payload. The reason is that the property lookup was time consuming. This information will return again in Infrahub 1.2 with a completely updated format. ([#5664](https://github.com/opsmill/infrahub/issues/5664))

### Fixed

- Fix nodes remaining in the database after a create mutation fails when using pools. ([#4303](https://github.com/opsmill/infrahub/issues/4303))
- Modify the query for the current tasks, ensuring the correct determination of the merge button state. ([#5565](https://github.com/opsmill/infrahub/issues/5565))
- Fix Docker `task-manager-db` PostgreSQL health check test by adding database and user parameters. ([#5739](https://github.com/opsmill/infrahub/issues/5739))
- Fixed issue causing a gap in menu sidebar when text is too long.
- Prevent avatar from being cut off in menu sidebar.
- Enforce permission checks when using relationship add or delete mutation.
- Enhance the data integrity checks UI to enable navigation from the check to the diff view.
- Improved performance when updating an existing diff.

## [Infrahub - v1.1.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.6) - 2025-01-30

### Artifact improvements

As part of our ongoing efforts to enhance the integrations and capabilities of Infrahub, the Artifact detail page has been redesigned.

This redesign focused on allowing a richer and more powerful Artifact experience.
Enhancements include support for additional content-types (as listed below), colorized syntax highlighting, and easier access to download or copy artifacts.

**Supported Artifact Content Types**:

- Markdown
- YAML
- JSON
- Text
- SVG

### Added

- Allow Default Address Type quick selection in the Resource Manager form ([#3489](https://github.com/opsmill/infrahub/issues/3489))
- Added code viewer for new content-types, preview of raw markdown content, one-click file download or cop, and redesign of artifact details view ([#5452](https://github.com/opsmill/infrahub/issues/5452))

### Fixed

- Automatically mark hierarchical nodes `parent` relationship as optional if the parent is of the same kind or mandatory if the parent is of a different kind ([#3682](https://github.com/opsmill/infrahub/issues/3682))
- Revert back to `state=open` from `state=merging` if the merge of a proposed change fails.
  This fixes the possibility of leaving a proposed change in an unexpected state. ([#5563](https://github.com/opsmill/infrahub/issues/5563))
- Fixes an issue with retrieving object from S3 storage backend. ([#5573](https://github.com/opsmill/infrahub/issues/5573))
- Loosened requirement for group discovery using OIDC and id_token. This will probably be reverted or presented as a configuration option in the future. ([#5623](https://github.com/opsmill/infrahub/issues/5623))
- Significant improvements to diff calculation performance.

## [Infrahub - v1.1.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.5) - 2025-01-24

### Added

- Allow OIDC providers to fall back to id_token for group membership reports if they are not provided within the `userinfo` URL. This allows for group support using Azure. ([#5464](https://github.com/opsmill/infrahub/issues/5464))
- Add computed attributes display in schema visualizer to display the Jinja2 and Python transforms details. ([#5515](https://github.com/opsmill/infrahub/issues/5515))

### Fixed

- Prevent branches in a remote Git repository from being imported if they have conflicts. This can be checked in the repository task logs. ([#5085](https://github.com/opsmill/infrahub/issues/5085))
- Correct the form to ensure it retrieves all values from the profile accurately. ([#5276](https://github.com/opsmill/infrahub/issues/5276))
- Fix the multi select update mutation when removing all items. ([#5334](https://github.com/opsmill/infrahub/issues/5334))
- Fix parent filter rule for relationships in forms to not mark as required if the field is required. ([#5418](https://github.com/opsmill/infrahub/issues/5418))
- Ensure Transforms are executed with the correct timeout. ([#5456](https://github.com/opsmill/infrahub/issues/5456))
- Fix unexpected `Too many relationships` error while retrieving multiple nodes having the same parent. ([#5474](https://github.com/opsmill/infrahub/issues/5474))
- The name of generated artifacts is now using `artifact_name`, from the artifact definition, instead of the name of the definition itself. Existing artifacts will be renamed the next time they are generated. ([#5484](https://github.com/opsmill/infrahub/issues/5484))
- Switch Docker health check from `/api/schema/summary` to `/api/config`, to ensure that the health check works when Infrahub is configured to disallow anonymous read access. ([#5522](https://github.com/opsmill/infrahub/issues/5522))
- Improved format of data and schema integrity error messages on a Proposed Change to include more information.

## [Infrahub - v1.1.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.4) - 2025-01-17

### Removed

- Removed configuration option for experimental feature "pull request", since this feature was active in the configuration it has been renamed proposed change and is no longer experimental but always enabled. ([#5409](https://github.com/opsmill/infrahub/issues/5409))

### Added

- Artifacts can now be of type: YAML, XML, markdown, SVG and CSV. ([#5452](https://github.com/opsmill/infrahub/issues/5452))

### Changed

- Updated Infrahub SDK to version 1.6.1.

### Fixed

- Fix issue when loading multiple schema files due to load order, schemas are now merged into a single one before importing ([#4188](https://github.com/opsmill/infrahub/issues/4188))
- Accessibility improvements to homepage: Helper cards now scale based on user's defined font size.
- Task status indicators now poll for updates only when tab is focused.

## [Infrahub - v1.1.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.3) - 2025-01-16

### Added

- Add a new link in the object details button to redirect to the tasks list with a filter for the current object

### Changed

- Add ID and HFID copy buttons in a new action buttons for the object details ([#4648](https://github.com/opsmill/infrahub/issues/4648))
  - Remove the ID attribute from the list
  - Get the description from the object if that's possible, if not then from the schema
- Disable action buttons depending on the on going tasks for the different workflows (merge, rebase, validate)
- Display multiple related nodes in the tasks list and details views
- Changed the default value for the s3.default_acl configuration setting to `private`

### Fixed

- Prevent access to REST API endpoints for anonymous user when anonymous access is not allowed ([#5312](https://github.com/opsmill/infrahub/issues/5312))
- Fix pool exhaustion error for IP resource pools when some allocated nodes were deleted ([#5315](https://github.com/opsmill/infrahub/issues/5315))
- Fix IP address being displayed in IP prefix pool after deleting the allocated prefix it was part of ([#5316](https://github.com/opsmill/infrahub/issues/5316))
- Fixed text overflow when there is too many options when selecting a relationship with a hierarchical model ([#5431](https://github.com/opsmill/infrahub/issues/5431))
- Allow to change any attributes and relationships when using a mutation on `CoreAccount` ([#5455](https://github.com/opsmill/infrahub/issues/5455))
- Validate updates to an attribute's `kind` when loading a new schema ([#5460](https://github.com/opsmill/infrahub/issues/5460))

## [Infrahub - v1.1.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.2) - 2025-01-09

### Added

- Added a configuration option for INFRAHUB_PUBLIC_URL, which could be required for SSO depending on how Infrahub is published and accessed within your organization. ([#5306](https://github.com/opsmill/infrahub/issues/5306))
- Add `PermissionManager` that takes care of validating permissions when executing a GraphQL query or a requesting a REST endpoint by fetching permissions from backends only once per query. ([#5350](https://github.com/opsmill/infrahub/issues/5350))
- The query InfrahubTask in GraphQL, introduced a new `related_nodes` field to retrieve multiple related nodes per task.

### Changed

- The fields `related_node` and `related_node_kind` on the GraphQL query `InfrahubTask` have been deprecated, please use `related_nodes` instead.

### Fixed

- Fix schema dropdown option removal in branches other than the default one ([#5242](https://github.com/opsmill/infrahub/issues/5242))
- Fix an issue that would prevent creating a node on a branch with a computed attribute that referenced another node on that branch ([#5385](https://github.com/opsmill/infrahub/issues/5385))
- Update how we calculate an incremental diff to skip potentially expensive operations if at all possible
- Update uniqueness checks/constraints logic to consider NULL values instead of ignoring.
  This might cause data integrity issues if you have nodes with NULL values for attributes that are part of their
  the uniqueness constraints of their schema. This change includes a database migration that validates data integrity
  using the new uniqueness check/constraint logic and will fail if any uniqueness issues exist.

## [Infrahub - v1.1.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.1) - 2025-01-05

### Fixed

- Raise a better error when trying to resolve an invalid HFID for a relationship ([#5360](https://github.com/opsmill/infrahub/issues/5360))
- Fix an issue with session management that could lead to the crash of the GraphQL resolver
- Fix query response time when the number of historical value for a given attribute is large
- Fixed an issue that prevented using an IP Namespace on a branch

## [Infrahub - v1.1.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.1.0) - 2024-12-30

### Removed

- Remove at parameter from GraphQL mutate functions ([#3587](https://github.com/opsmill/infrahub/issues/3587))
- Remove the "role" attribute of base schema account node. This attribute was no longer useful as roles are defined as dedicated nodes and are tightly related to permissions.
- Remove the /api/diff/data and /api/diff/schema endpoints that have been replaced by the DiffTree GraphQL query

### Added

- Add support for computed attributes. The computed attributes allows you to define a schema attribute as read only and provide logic for how the attribute should be updated. The logic that updates a computed attribute can be a Jinja2 template or a Python Transform. Aside from the initial creation when using a Jinja2 template the updates will be done asynchronously in the background. ([#3637](https://github.com/opsmill/infrahub/issues/3637))
- Add a "deprecation" property to attribute and relationship schema in order to allow users to identify deprecated fields for nodes and provide a user-friendly message about the deprecation reasons. ([#4245](https://github.com/opsmill/infrahub/issues/4245))
- Enhanced relationship inputs for hierarchical models with a new way to navigate and select objects directly within the hierarchy. ([#4636](https://github.com/opsmill/infrahub/issues/4636))
- Add ability to use node HFID to create a related node on a generic relationship ([#4649](https://github.com/opsmill/infrahub/issues/4649))

### Changed

- More efficient logic for retrieving cardinality-one relationships within a GraphQL query ([#522](https://github.com/opsmill/infrahub/issues/522))
- Change strings referring to file system paths to pathlib.Path objects ([#3545](https://github.com/opsmill/infrahub/issues/3545))
- Improved response time of menu endpoint

### Fixed

- Fix search anywhere so it looks at Groups ([#3173](https://github.com/opsmill/infrahub/issues/3173))
- Display the IP Namespace for prefixes and IP addresses in the search anywhere ([#3577](https://github.com/opsmill/infrahub/issues/3577))
- Use the repository object ID as name for its git working copy directory ([#4296](https://github.com/opsmill/infrahub/issues/4296))
- Search anywhere now supports IPv6 extended format ([#4613](https://github.com/opsmill/infrahub/issues/4613))
- - Update action buttons UI in the branch details view
  - Pre-fill the source branch select when creating a proposed change from the branch details view
  ([#4678](https://github.com/opsmill/infrahub/issues/4678))
- Synchronise git repository clones and updates for task workers in order to remove the need for a shared storage ([#4789](https://github.com/opsmill/infrahub/issues/4789))
- FIX: Resolved edge cases in 'Search Anywhere' that were causing old results to be displayed. ([#4863](https://github.com/opsmill/infrahub/issues/4863))
- Remove Profile in registry for renamed schema nodes ([#4909](https://github.com/opsmill/infrahub/issues/4909))
- Forbid changing the "optional" property of an inherited attribute to not break GraphQL schema generation ([#4936](https://github.com/opsmill/infrahub/issues/4936))
- Send a request to the backend on logout to delete session cookies and prevent remaining information ([#4962](https://github.com/opsmill/infrahub/issues/4962))
- Fix query to correctly send the variables in the tasks details view ([#5002](https://github.com/opsmill/infrahub/issues/5002), [#5118](https://github.com/opsmill/infrahub/issues/5118))
- Update alerts type on errors with proposed changes and branches ([#5293](https://github.com/opsmill/infrahub/issues/5293))
- - Verify the tasks related to the proposed changes view to show or hide the tasks accordion in the details view
  - Disable the merge button if there is an ongoing merge
  - Add poll-interval to the proposed changes query to be up to date on the state and disable the merge button if the proposed change is already merged
- Add support for irresolvable conflicts to the diff logic and DiffTree GraphQL query
- Fix a bug that prevented updating a relationship during a merge if ONLY the metadata was updated and not the peer.
- Fix permission check when using multiple backends, if one grants a permission the next ones must not be queried.
- Update logic to check if the changes on a branch include schema changes to use the new diff
- Update the api/diff/artifacts endpoint to use a dedicated query
- Verify if the requested branch exists. If it doesn't, it redirects to the homepage on the default branch.

  This helps avoid query issues, such as empty results (for example, an empty menu) or incorrect queries being sent.

## [Infrahub - v1.0.10](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.10) - 2024-12-20

### Added

- Make URL fields clickable in the details view ([#5005](https://github.com/opsmill/infrahub/issues/5005))

### Fixed

- Support directionality in the query to get all peer IDs for a given group of nodes ([#3065](https://github.com/opsmill/infrahub/issues/3065))
- Fix errors when executing `infrahub db update-core-schema` command that were impacting migrations from prior versions ([#5186](https://github.com/opsmill/infrahub/pull/5186), [#5254](https://github.com/opsmill/infrahub/pull/5254))

## [Infrahub - v1.0.9](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.9) - 2024-12-13

### Added

- Adding `invoke` tasks to assist with release process. ([#4519](https://github.com/opsmill/infrahub/issues/4519))
- Add pagination and backend search in new combobox for relationships.
- Added custom Towncrier template to remove extra space after new Changelog entries.
- In schema viewer, we now display `Hierarchical` value for generics.

### Fixed

- Update delete constraints to correctly account for relationships on generics and relationships for which the peer kind is a generic. ([#4332](https://github.com/opsmill/infrahub/issues/4332))
- Fix error when `pool` was used a relationship name. ([#4807](https://github.com/opsmill/infrahub/issues/4807))
- Ensure that deleted schema nodes are removed from all workers and that the schema is in sync without having to restart. ([#4836](https://github.com/opsmill/infrahub/issues/4836))
- Consistently use "Save" on all object forms submit buttons. ([#4850](https://github.com/opsmill/infrahub/issues/4850))
- Search shortcuts show `Cmd` on macOS and `Ctrl` on other systems. ([#4861](https://github.com/opsmill/infrahub/issues/4861))
- Update the parent relationship query to populate the dropdown options when editing an object, ensuring the current parent is correctly selected for the current node. ([#5035](https://github.com/opsmill/infrahub/issues/5035))
- Correctly refresh menu after access token has expired. ([#5099](https://github.com/opsmill/infrahub/issues/5099))
- On the object permission form, fix the name option selection when changing the namespace to get the latest options and to be able to choose a name option. ([#5100](https://github.com/opsmill/infrahub/issues/5100))
- Prevent adding a new mandatory attribute or relationship to the schema if some nodes are already present in the database. ([#5106](https://github.com/opsmill/infrahub/issues/5106))
- Refresh branch hash on local worker during branch create. ([#5130](https://github.com/opsmill/infrahub/issues/5130))
- Fix uniqueness constraint check with enum based attributes. ([#5132](https://github.com/opsmill/infrahub/issues/5132))
- Editing old `CHANGELOG.md` entries to use uniform formatting from new Towncrier template.
- Store CoreProfile in database to ensure consistent initial schema hash. Prior to this the schema was reported as being out of sync when starting the application for the first time. This error wouldn't have hade any impact but was confusing. The workaround would be to load a schema or restart the application at least once after first time initialization.
- Use the branch uuid instead of the internal database id to track the hash of the schema in the cache.

## [Infrahub - v1.0.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.8) - 2024-12-03

### Added

- Add `sso_user_default_group` security setting to provide the name of a group to which SSO users will be assigned if the identity provider does not gives a list of groups to use ([#4924](https://github.com/opsmill/infrahub/issues/4924))
- Added a 'append_git_suffix' configuration setting for Git repositories that allows you to define domains for auto appending '.git' to repositories defined with an HTTP URL ([#5077](https://github.com/opsmill/infrahub/issues/5077))

### Fixed

- Loosened up logic to determine when an artifact needs to be regenerated during a proposed change. This is to ensure that we always generate a new artifact if required. Until some other parts are refactored this will also need that we will generate artifacts in a few situations where it's not strictly required. This last part is a temporary solution. ([#4198](https://github.com/opsmill/infrahub/issues/4198))
- Migrates from headless UI combobox to `cmdk` to resolve focus behavior issues when there is no result in the search anywhere ([#4715](https://github.com/opsmill/infrahub/issues/4715))
- Fix GraphQL mutations to make user permissions updates work correctly
  - Update the alert message to better reflect the changes (between creation and update)
  - Fix the objects delete modal on the global permission view
  - Fix the global permission update mutation

  ([#4881](https://github.com/opsmill/infrahub/issues/4881), [#4952](https://github.com/opsmill/infrahub/issues/4952))
- Validate that a deleted schema node is not used in any relationship when loading a new schema ([#4912](https://github.com/opsmill/infrahub/issues/4912))
- Set content type of artifact when rendered to fix artifact content type if artifact definition has changed ([#4969](https://github.com/opsmill/infrahub/issues/4969))
- Raise error if pool allocation misses data to create node ([#5006](https://github.com/opsmill/infrahub/issues/5006))
- Process new schema before replacing branch in registry to avoid causing the GraphQL schema to be generated while the new schema is still loading ([#5008](https://github.com/opsmill/infrahub/issues/5008))
- Added a check on repository import and sync to wait until the schema has converged before importing additional objects when the repository contains an updated schema ([#5051](https://github.com/opsmill/infrahub/issues/5051))
- Fix artifact definition targets when changed in repository so that it's reflected in the database ([#5060](https://github.com/opsmill/infrahub/issues/5060))
- GraphQL query with filters on attribute of type List return the expected result ([#5091](https://github.com/opsmill/infrahub/issues/5091))
- Prevent adding a new mandatory attribute or relationship to the schema if some nodes are already present in the database ([#5106](https://github.com/opsmill/infrahub/issues/5106))
- Ensure that permission queries are run in non isolated mode so that updates from the default branch are automatically reflected in other branches ([#5110](https://github.com/opsmill/infrahub/issues/5110))
- Add retry for transient database errors during IP reconciliation tasks
- Corrected configuration for prefect worker to never prompt for Git credentials on the console
- Fix artifact object relationship by enforcing it to be an artifact target
- Fix bug in IP reconciliation query around deleted nodes and relationships
- Fix issue that could cause diff generation to crash if a schema was renamed
- Fixes a bug that prevented running a generator from a read-only repository
- Generator groups are correctly created after merging a proposed change

## [Infrahub - v1.0.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.7) - 2024-11-20

### Fixed

- Fix permission issue with Repository management ([#4976](https://github.com/opsmill/infrahub/issues/4976))
- Fix bug that prevented setting an attribute to NULL as part of a merge ([#4996](https://github.com/opsmill/infrahub/issues/4996))
- Fix a bug in the query to delete a relationship that could create unnecessary "deleted" edges on the database
- Fix bug in incremental diff addition for nodes within a hierarchy

## [Infrahub - v1.0.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.6) - 2024-11-18

### Fixed

- Forbid changing the "optional" property of an inherited attribute to not break GraphQL schema generation ([#4936](https://github.com/opsmill/infrahub/issues/4936))
- Permission edit_default_branch is now enforced properly when loading a schema ([#4958](https://github.com/opsmill/infrahub/issues/4958))
- Session is now correctly cleared when logging out from the web UI ([#4962](https://github.com/opsmill/infrahub/issues/4962))
- Anonymous user will get a 401 response when trying to load a schema

## [Infrahub - v1.0.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.5) - 2024-11-15

### Fixed

- Node attribute name can now be `type` ([#4381](https://github.com/opsmill/infrahub/issues/4381))

## [Infrahub - v1.0.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.4) - 2024-11-13

### Fixed

- Profiles now have a Human-Friendly Identifier (HFID) defined based on `profile_name` ([#4758](https://github.com/opsmill/infrahub/issues/4758))
- Workers out of sync after deleting node from schema ([#4836](https://github.com/opsmill/infrahub/issues/4836))
- Infrahub returns a proper error message when trying to load a schema with generic with the same Kind as an existing node ([#4837](https://github.com/opsmill/infrahub/issues/4837))
- Default to using HTTP GET for UserInfo endpoints (OAuth2/OIDC) ([#4898](https://github.com/opsmill/infrahub/issues/4898))
- Remove Profile in registry for renamed schema nodes ([#4909](https://github.com/opsmill/infrahub/issues/4909))

## [Infrahub - v1.0.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.2) - 2024-11-08

### Fixed

- Fix hierarchical schema update logic to correctly update peer on parent relationship of new node ([#4838](https://github.com/opsmill/infrahub/issues/4838))
- Fix hierarchical schema update logic to correctly update peer on parent of new child node ([#4839](https://github.com/opsmill/infrahub/issues/4839))
- Define the version of numpy to install in pyproject.toml

## [Infrahub - v1.0.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.2) - 2024-11-06

### Fixed

- Update branch merge logic to use smaller queries outside of a transaction to allow merging a branch with many changes ([#4448](https://github.com/opsmill/infrahub/issues/4448))
- Ensure the GraphQL query InfrahubResourcePoolUtilization works properly when the schema is different in the branch ([#4761](https://github.com/opsmill/infrahub/issues/4761))

## [Infrahub - v1.0.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.1) - 2024-10-31

### Fixed

- When a user is not logged in and the branch name is not found, hide the quick-create action and display the message: 'No branch found' ([#4801](https://github.com/opsmill/infrahub/issues/4801))
- Fix automation to trigger generation of artifacts after merging a branch ([#4804](https://github.com/opsmill/infrahub/issues/4804))
- Avoid sending an empty list to the load schema API on repository import if it's not required
- Update demo environment to work with Infrahub 1.0

## [Infrahub - v1.0.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.0.0) - 2024-10-30

### Removed

- Remove previously deprecated GET API endpoint "/api/schema/" ([#3884](https://github.com/opsmill/infrahub/issues/3884))

### Deprecated

- Marked CoreAccount.role as deprecated
  Due to the new permissions framework the account roles "admin" / "read-only" / "read-write" are deprecated and will be removed in Infrahub 1.1

### Added

- Reworked branch selector:
  - Redesigned the UI
  - Added filter for branch
  - Improved accessibility & keyboard navigation
  - Improved UX on new branch form
  - Added quick link to view all branches
- Add support to sign in with OAuth2 and Open ID Connect (OIDC) ([#1568](https://github.com/opsmill/infrahub/issues/1568))
- Add internal HTTP adapter to allow for generic access from Infrahub ([#3302](https://github.com/opsmill/infrahub/issues/3302))
- Add support to search a node by human friendly ID within a GraphQL query ([#3908](https://github.com/opsmill/infrahub/issues/3908))
- Added link to our Discord server in the account menu
- Added permissions framework for global and object kind level permissions

  In this first iteration the object permissions are applied to nodes as a whole, in upcoming versions it will be possible to define attribute level permissions as well.
- New permissions system in UI:
  - Implemented CRUD views for managing accounts, groups, roles, and permissions
  - Updated all components to support new permission system
  - Added dynamic message display according to user access levels

### Fixed

- The `infrahub-git` agent service has been renamed to `task-worker` in Docker Compose and the command to start it has been updated as well ([#1075](https://github.com/opsmill/infrahub/issues/1075))
- Add ability to import repositories with default branch other than 'main' ([#3435](https://github.com/opsmill/infrahub/issues/3435))
- Disable approve/merge/close buttons for merged Proposed Changes ([#3495](https://github.com/opsmill/infrahub/issues/3495))
- Fixed regex validation for List type attributes ([#3929](https://github.com/opsmill/infrahub/issues/3929))
- Allow users to run artifacts and generators on nodes without name attribute ([#4062](https://github.com/opsmill/infrahub/issues/4062))
- In the schema, properly delete inherited attribute and relationship on Node when the original attribute or relationship are being deleted on the Generic ([#4301](https://github.com/opsmill/infrahub/issues/4301))
- "Retry All" button for checks is bigger ([#4315](https://github.com/opsmill/infrahub/issues/4315))
- Add a size restriction on common attribute kinds. Only TextArea and JSON support large values ([#4432](https://github.com/opsmill/infrahub/issues/4432))
- The HFID of a related node is properly returned via GraphQL in all scenarios ([#4482](https://github.com/opsmill/infrahub/issues/4482))
- Add full validation to BranchMerge and BranchRebase mutations ([#4595](https://github.com/opsmill/infrahub/issues/4595))
- Report user-friendly error for invalid uniqueness_constraints when loading schemas ([#4677](https://github.com/opsmill/infrahub/issues/4677))
- Fixed pagination query for nodes with order_by clause using non unique attributes ([#4700](https://github.com/opsmill/infrahub/issues/4700))
- Fixed schema migration when an attribute previously present on a node is added back ([#4727](https://github.com/opsmill/infrahub/issues/4727))
- Add order_weight property to multiple attributes and relationships in the demo schema to improve how some models are displayed in the list views
- Changed the Python SDK connection timeout to 60s
- Fix metric missing the query name in Prometheus data
- Fixes an issue where Docker Compose would output ANSI control characters that don't support it
- Prevent temporary directories generated by Docusaurus to be imported by Docker

## [Infrahub - v0.16.4](https://github.com/opsmill/infrahub/tree/infrahub-v0.16.4) - 2024-10-17

### Fixed

- Fixed an issue on the UI where a new relationship was being added to the main branch instead of the current branch. ([#4598](https://github.com/opsmill/infrahub/issues/4598))

## [Infrahub - v0.16.3](https://github.com/opsmill/infrahub/tree/infrahub-v0.16.3) - 2024-10-10

### Removed

- Removed `infrahub.toml` configuration file from Docker builds.

### Fixed

- Save a diff in smaller pieces instead of all at once to prevent out-of-memory error. ([#4511](https://github.com/opsmill/infrahub/issues/4511))
- Fixes exception handling section in the Python SDK batch guide.

## [Infrahub - v0.16.2](https://github.com/opsmill/infrahub/tree/infrahub-v0.16.2) - 2024-10-01

### Fixed

- Loading a schema with an invalid order_by field raise a proper error. ([#4323](https://github.com/opsmill/infrahub/issues/4323))
- Updates internal logic to improve performance when generating a diff.

  BREAKING CHANGE: Diff data, including conflict selections, will be deleted. We recommend merging
  any outstanding proposed changes before upgrading to this version. ([#4438](https://github.com/opsmill/infrahub/issues/4438))
- Fix performance issue for GraphQL queries that only count nodes. ([#4454](https://github.com/opsmill/infrahub/issues/4454))
- Fix ability to construct HFID for upsert mutations where a number attribute is used. ([#4460](https://github.com/opsmill/infrahub/issues/4460))

## [Infrahub - v0.16.1](https://github.com/opsmill/infrahub/tree/infrahub-v0.16.1) - 2024-09-24

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

## [Infrahub - v0.16.0](https://github.com/opsmill/infrahub/tree/infrahub-v0.16.0) - 2024-09-11

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

## [Infrahub - v0.15.3](https://github.com/opsmill/infrahub/tree/infrahub-v0.15.3) - 2024-08-13

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
