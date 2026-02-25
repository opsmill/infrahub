# Infrahub changelog

This is the changelog for Infrahub.
All notable changes to this project will be documented in this file.

Issue tracking is located in [GitHub](https://github.com/opsmill/infrahub/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub/tree/develop/infrahub/changelog/>.

<!-- towncrier release notes start -->

## [Infrahub - v1.7.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.6) - 2026-02-24

### Fixed

- Pass order weights into Profile schema fields to prevent reordering causing a hash mismatch

## [Infrahub - v1.7.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.5) - 2026-02-23

### Removed

- Removed unused `enable` configuration toggle from broker, cache, and workflow settings

### Fixed

- Add migration to handle setting duplicated schemas on the default branch to be deleted, keeping the one with the latest update ([#8221](https://github.com/opsmill/infrahub/issues/8221))
- Handle deleted parent relationship schemas when combining diffs without crashing ([#8388](https://github.com/opsmill/infrahub/issues/8388))
- Prevent saving generated "profiles" and "object_template" schema relationships to the database. Includes a migration to clean up any already on the database. ([#8426](https://github.com/opsmill/infrahub/issues/8426))
- Fixed regression (introduced in Infrahub 1.5) regarding merge performance. ([#8438](https://github.com/opsmill/infrahub/issues/8438))
- Add full support for updating existing Template instances via schema migrations when the associated node or generic schema is updated in a manner that would add or remove attributes to or from the Template's schema.
- Adds automatic retries to database queries during a branch merge to handle transient errors
- Allow generating Template schemas for both a generic schema and a node inheriting from that generic. Previously, schema validation would raise a validation error and prevent this.
- Fixed an issue where Infrahub was calculating the wrong authentication signature caused by HTTPX v0.28.0 switching to compact JSON payload encoding.
- Fixed issue where system user showed as the last user changing a proposed change after merge

## [Infrahub - v1.7.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.4) - 2026-02-03

### Removed

- Removed references to the deprecated `is_visible` metadata property from documentation.

### Fixed

- Fix bug in computed attribute calculation that prevented having a computed attribute on a branch if there were no computed attributes on the default branch ([#8270](https://github.com/opsmill/infrahub/issues/8270))
- Add migration to allow rebasing branches created before #8221 was fixed so that the uniqueness constraint on SchemaNode.name and SchemaGeneric.name is removed
- Fixed branch merge failing to include relationships to AGNOSTIC nodes (e.g., CoreIPAddressPool) by including the global branch in the peer node lookup query.
- Fixed confusing issue when "off" was converted to boolean 'false' due to issues with Yaml. The bug was that if "off" or something that Yaml parses as a boolean was used as the name of a Dropdown the incorrect attribute was highlighted in the schema error. When this happened troubleshooting was harder due to misleading errors pointing to another attribute.

## [Infrahub - v1.7.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.3) - 2026-01-28

### Security

- Update system dependencies: OpenSSL patch for CVE-2025-15467

### Fixed

- Single line breaks in text fields are now rendered correctly.

## [Infrahub - v1.7.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.2) - 2026-01-27

### Added

- Added "parallel mode" plugin to the GraphQL web sandbox.
- GraphQL query parsing and validation is now leveraging a cache to improve performance and CPU consumption.

### Changed

- Infinite scrolling now fetches more entries per page when having a lot of objects. ([#8057](https://github.com/opsmill/infrahub/issues/8057))

### Fixed

- Fixed issue around the use of the validate_certificates attribute on webhooks. This change also modifies this attribute so that it no longer has a default value, instead the Infrahub default configuration for HTTP is used and the attribute is only to override the default. ([#6308](https://github.com/opsmill/infrahub/issues/6308))
- Fixed a bug that caused branch-agnostic attributes on branch-aware objects to be deleted globally when the object was deleted. Now branch-agnostic attributes on branch-aware objects are only deleted on the branch where the object was deleted. ([#7513](https://github.com/opsmill/infrahub/issues/7513))
- Figure number and IPAM resources to allocate from a pool by using Cypher queries instead of iterating logic, this should fix timeout observed when allocating resources within large pools ([#7897](https://github.com/opsmill/infrahub/issues/7897))
- Fixed an issue where parallel create or update operations would attach multiple peers to a cardinality one relationship. ([#7972](https://github.com/opsmill/infrahub/issues/7972))
- Search anywhere bar now scale with the number of objects within Infrahub.
  Cardinality many relationships are now ignored and not shown in search results. ([#8059](https://github.com/opsmill/infrahub/issues/8059))
- Prevent opening a proposed change if there is already an open proposed change for the branch. ([#8123](https://github.com/opsmill/infrahub/issues/8123))
- Fix bug in node create logic that could cause edges to be added to the database with the wrong hierarchy level on the global branch. Includes a migration to fix existing problem edges. ([#8158](https://github.com/opsmill/infrahub/issues/8158))
- Fix bug in node create logic that could cause branch-local edges to be added to the database with the wrong hierarchy level. Includes a migration to fix existing problem edges. ([#8159](https://github.com/opsmill/infrahub/issues/8159))
- Fix diff update logic to prevent crash when copying a diff with recursive relationships ([#8165](https://github.com/opsmill/infrahub/issues/8165))
- Update branch delete logic to correctly delete branch-agnostic attributes from objects being deleted with the branch. Includes a migration to clean up any orphaned objects with branch-agnostic attributes left in the database. ([#8211](https://github.com/opsmill/infrahub/issues/8211))
- Prevent creating duplicate schemas on branches and merging them into the default branch ([#8221](https://github.com/opsmill/infrahub/issues/8221))
- Fixed an issue where unexpected restarts of tasks workers would result in tasks being in "Running" state forever.
  As a side effect, this would block Git repositories sync tasks to be launched. ([#8227](https://github.com/opsmill/infrahub/issues/8227))
- Fixed an issue causing overfetching in IPAM tree
- When using local docs, icons and images are correctly loaded.

## [Infrahub - v1.7.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.1) - 2026-01-12

### Added

- Added option to use username/password authentication on Redis connections ([#7994](https://github.com/opsmill/infrahub/issues/7994))

### Fixed

- Fix failing execution of unit tests within a proposed change pipeline. ([#8075](https://github.com/opsmill/infrahub/issues/8075))

## [Infrahub - v1.7.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.0) - 2026-01-08

We're excited to announce the release of Infrahub, v1.7.0! This release focuses on enhancing data governance and strengthening the platform foundation for enterprise deployments.

Version 1.7 introduces comprehensive audit capabilities with immutable metadata tracking, expands profile functionality to support relationships. Under the hood, we've upgraded critical backend dependencies to ensure optimal performance, security, and long-term maintainability.

### Main changes

#### Object level meta data

Infrahub now automatically tracks who created and last modified every object in your infrastructure data. This foundational capability enables complete audit trails and accountability across your entire automation stack.

Every object now includes:

- **Created by** and **updated by** — user attribution for all changes
- **Created at** and **updated at** — precise timestamps for data lifecycle tracking

This metadata is available through the UI, GraphQL API and Python SDK, enabling you to determine who created or updated an object and at which time.

The metadata is read-only and survives across branch operations, ensuring you have a reliable audit trail even in complex version control workflows.

This positions Infrahub as enterprise-ready for organizations requiring detailed data provenance and accountability.

The `created_at` and `updated_at` metadata will be set for all objects, even those that were create before this feature.
The `created_by` and `updated_by` metadata will be set for objects that have been created or updated after this release, existing objects will not be backfilled.

#### Relationships in Profiles

Profiles now support relationships in addition to attributes, enabling you to define complete, reusable templates for entire classes of objects.

Previously, profiles could only set attribute values, limiting their usefulness and adoption. Now you can:

- Define relationships within a profile alongside attributes
- Create comprehensive templates that capture both data and connections
- Enforce data consistency across large inventories with less manual work
- Apply complete object configurations at scale

Additionally profiles now support required attributes and relationships, as long as they are not part of a uniqueness constraint.

For example, you can now create a "Production Server Interface" profile that captures configurations, such as the speed and MTU and mode, but also automatically connect it to a specific VLAN.

This reduces manual configuration, minimizes errors when scaling automation projects, and ensures that relationships are consistently applied across your infrastructure data model.

#### Branch list page scaling

Several users of Infrahub, have a requirement to have a large number of branches active at any given time in Infrahub. The branch list page has been updated to provide a better user experience when you have a large number of branches.

The branch list page now uses the previously introduced `InfrahubBranch` GraphQL query, which provides pagination functionality for the branch query. In this release we have also introduced a `partial_match` filter, which allows a user to search for a branch by a partial name.

Additionally the branch list page displays the new object level metadata, which allows you to more easily find the branch that you are looking for.

#### Redesigned object detail view

The object detail page has been significantly improved to provide better access to key information and actions.

Header improvements:

- New info icon provides quick access to the new object-level metadata
- Action button was redesigned and relocated for better accessibility
- New dedicated button to navigate directly to the object's schema definition
- Refreshed button styling

Groups management:

- New dedicated section displays all groups the object belongs to
- Easily add or remove the object from groups without navigating away

Profiles management:

- New section shows all profiles currently applied to the object
- Manage profile assignments directly from the object detail view

These changes make it faster to understand an object's context (its metadata, groups, and profiles) without switching between multiple views.

#### Upgraded backend dependencies

The platform foundation has been strengthened with major version upgrades across all core backend components:

- **Python**: 3.12 → 3.13
- **Neo4j**: 2025.03 → 2025.10/11
- **RabbitMQ**: 3.13 → 4.2
- **Redis**: 7.2 → 8.x
- **PostgreSQL**: 14 → 18

These upgrades deliver:

- Enhanced performance across the platform
- Improved security with the latest patches
- Access to new features in underlying technologies
- Better long-term maintainability and support

The upgrades have been thoroughly tested to ensure compatibility and performance regression has been validated to maintain Infrahub's reliability standards.

### Infrahub Python SDK

Infrahub v1.7.0 requires the usage of [infrahub-sdk v1.18.0](https://github.com/opsmill/infrahub-sdk-python/releases/tag/v1.18.0), please update the `infrahub-sdk` package accordingly.

### Full changelog

#### Deprecated

- Deprecated the '_updated_at' query field for GraphQL queries. The new node metadata field should be used instead. The '_updated_at' field will be completely removed in Infrahub 1.9.

#### Added

- Add search functionality to the branches list view, allowing users to filter branches by name. ([#2107](https://github.com/opsmill/infrahub/issues/2107))
- Added ability to enable and disable webhooks ([#6761](https://github.com/opsmill/infrahub/issues/6761))
- Added option to use username/password authentication on Redis connections ([#7994](https://github.com/opsmill/infrahub/issues/7994))
- Add display label based GraphQL filters `display_label__isnull`, `display_label__value` and `display_label__values`
- Added metadata display in branch list view showing last rebase, last update, created at, and created by information
- Added partial_match parameter to InfrahubBranch query for case-insensitive substring filtering on branch names
- Display "No task" on branch details when task are empty.
- Improved menu in IPAM details view:

  - Replaced the three-dot menu with a clearly labeled Actions button to open menu
  - Added quick navigation to related tasks
  - Added convert object type action
  - Added icons for all menu items

#### Changed

- This refactors timestamp handling across query and relationship functions to accept only Timestamp types, updates all dependent code and tests accordingly, refreshes development environment files, and includes no user-facing changes. ([#63](https://github.com/opsmill/infrahub/issues/63))
- Improve branches list and details views to use the updated GraphQL API structure. ([#2108](https://github.com/opsmill/infrahub/issues/2108))
- Upgraded backend dependencies: Neo4j to 2025.10.1, Redis to 8.4.0, RabbitMQ to 4.2.1, PostgreSQL to 18

#### Fixed

- Fixed issue with creating and deleting webhook automations for installations with a high number of automations in Prefect.
- Fixed relationship fields not being cleared when removing a profile from a node
- Fixed the display order of attributes and relationships in detail views.
- Re-enable running a single migration in `infrahub db migrate` using the `--migration-number` option
- Updating your account information now correctly refreshes the visible data, preventing outdated data from being shown.

## [Infrahub - v1.6.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.6.3) - 2026-01-07

### Changed

- Changed DiffTreeSummary GraphQL type count fields to be non-optional ([#7778](https://github.com/opsmill/infrahub/issues/7778))

### Fixed

- Stop showing warnings for deprecated attribute schema fields (regex, min_length, max_length) when they are not used ([#7995](https://github.com/opsmill/infrahub/issues/7995))

## [Infrahub - v1.6.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.6.2) - 2025-12-22

### Fixed

- Fix Migration041 to determine edge uniqueness correctly and  account for incoming Relationship edges. Add new migration to un-delete improperly deleted Relationship metadata. This would only be a problem for Relationships between schemas that have both had their name, namespace, or kind updated multiple times. ([#7916](https://github.com/opsmill/infrahub/issues/7916))

## [Infrahub - v1.6.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.6.1) - 2025-12-11

### Added

- Add support for PKCE within Oauth2 and OIDC authentications. With this change the client_secret for Oauth2 and OIDC have been switched to being optional. PKCE is enabled by default but can be switched off in the configuration if required. ([#7400](https://github.com/opsmill/infrahub/issues/7400))

### Changed

- Upgrade infrahub-sdk to v1.17.0 ([#7870](https://github.com/opsmill/infrahub/pull/7870))

### Fixed

- Fix `display_label` not having a NULL value in the database when not set in the schema ([#7704](https://github.com/opsmill/infrahub/issues/7704))
- Fixed schema cache issue when adding or removing dropdown/enum options via the UI, which causes intermittent "incorrect hash" errors after page refreshes. ([#7780](https://github.com/opsmill/infrahub/issues/7780))
- Fix an issue where removing a mandatory relationship was allowed. ([#7853](https://github.com/opsmill/infrahub/issues/7853))
- Fix breadcrumb display on CoreArtifactDefinition details page.
- Fixed form submission for schemas with only read-only attributes
- Improve branch creation and repository sync performance when having a lot of branches.

## [Infrahub - v1.6.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.6.0) - 2025-12-01

We're excited to announce the release of Infrahub v1.6.0! This release brings significant improvements to Git integration, UI navigation, branch management, Profiles in Object Templates and introduces a new dashboard landing page.

### Main changes

#### New dashboard landing page

We've replaced the static landing page with an interactive dashboard so you can immediately see what's happening in your Infrahub environment. The interactive dashboard shows:

1. **Open proposed changes** with status and review state
2. **Git repositories** sync status
3. **Branches** with quick details
4. **Recent activity**  view the latest actions in Infrahub
5. **Tasks overview** the number of tasks that are running, completed, or that have failed.
6. **Getting started with Infrahub** – Access key resources like docs, labs, and tools.

#### Use Profiles in Object Templates

You can now define profiles in Object Templates so they're automatically applied when objects are created, ensuring consistency without manual post-creation steps.

#### Selective branch synchronization filter for Git repositories

Control which Git branches sync to Infrahub using configurable naming rules and patterns. Perfect for teams using multi-purpose repositories who want to keep Infrahub focused on relevant branches.

With this change you can now configure Infrahub to instead consult a list of branch names or regular expressions to determine if a given branch will be imported and created in Infrahub or not.

#### Explicit merge commits

Infrahub now optionally creates three-way merge commits instead of fast-forward merges, making it easy to trace Infrahub-originated merges in your Git repository history. You also have an option to configure the Git username and email that Infrahub will use to create the merge commit.

#### `infrahubctl branch report` command

The `infrahubctl branch report` command provides comprehensive status reports that help with branch cleanup and maintenance. When managing large environments with many branches, teams can now quickly identify which branches are safe to be removed.

The report displays:

- Branch metadata (creation time, sync status, schema changes)
- Git file changes detection
- Diff tree analysis with counts of added/updated/removed nodes
- Proposed changes summary with creator, approval status, and draft state

The `infrahubctl branch report` requires the installation of `infrahub-sdk` v1.16.0 with the `ctl` extra.

#### New breadcrumb navigation

Interactive breadcrumbs that adapt to your current view, show full object lineage, and let you switch between related objects directly.

#### Revamped hierarchy tree

We have redesigned the hierarchical tree to improve performance, and usability. This update addresses several long-standing issues and introduces a more intuitive navigation experience:

- Improved performance for large hierarchies
- Independent collapsing and navigation actions
- Resizable tree panel (10-50% of screen width)
- Smart loading when landing directly on detail views
- Better keyboard navigation and accessibility

#### Standardized label resolution in UI

All node labels will now resolve using this order:

1. If the schema defines a `display_label`, show `node.display_label`.
2. If not, but the schema defines an `hfid`, show `node.hfid`.
3. Otherwise, fall back to the node's `id`.

#### IPAM

The IPAM tree now uses the new hierarchy tree component (see changelog above) and is resizable.

#### Display Infrahub edition

See which Infrahub edition you're using in the account menu alongside the version.

#### Fixed nested `convert_query_response`

⚠ **BREAKING CHANGE**

When using `convert_query_response` with nested relationships in Python transforms and generators, queries must now include `id` and `__typename` fields on all nodes. This fixes a bug where objects were only converted one level deep.

If you are not using `convert_query_response` or if the queries that you are using with this feature aren't deeply nested, then you don't have to change anything.

### Full changelog

#### Added

- Templates now support profile assignment. When both `generate_template` and `generate_profile` are configured on a schema node, profiles can be assigned to templates and will be automatically inherited by objects created from those templates. Profiles provide values for attributes not explicitly configured on the template, while template values take precedence when manually set. Multiple profiles can be assigned with proper priority handling. This enables bulk configuration updates across templated objects while maintaining consistency through profile inheritance. ([#template-profiles](https://github.com/opsmill/infrahub/issues/template-profiles))
- Merge core read only repositories on branch merge ([#5978](https://github.com/opsmill/infrahub/issues/5978))
- IPAM tree is now resizable:

  - Adjust the width of the IPAM tree panel by dragging the divider
  - Tree panel can be resized between 10% and 50% of the screen width

  ([#7262](https://github.com/opsmill/infrahub/issues/7262))
- You can now see which Infrahub edition you're using, displayed next to the app version in the account menu. ([#7549](https://github.com/opsmill/infrahub/issues/7549))
- - Update the landing page documentation links to guide users in getting started with Infrahub.
  - Show Git repositories.
  - List branches on the landing page, sorted by creation date, with the main branch displayed first.
  - Include the proposed changes, showing only the key details.
  - Show recent activities, displaying only essential information.
  - Add tasks overview to display recent tasks and sort them by state.
- Add Explicit Merge Commits for Infrahub Branch Merges. These can be controlled via the INFRAHUB_GIT_USE_EXPLICIT_MERGE_COMMIT environment variable.
  The following environment variables are added:

  - INFRAHUB_GIT_USER_NAME
  - INFRAHUB_GIT_USER_EMAIL
  - INFRAHUB_GIT_GLOBAL_CONFIG_FILE
  - INFRAHUB_GIT_USE_EXPLICIT_MERGE_COMMIT

- Added branch filtering capability to selectively synchronize remote branches based on configurable import sync patterns.
- In the Proposed Changes data tabs, each node label is now a clickable link that takes you to the updated object’s detail page.
- New breadcrumb navigation:

  - Display full ancestors lineage of objects (parent objects or all ancestors for hierarchical schemas)
  - Display schema hierarchy for hierarchical schemas
  - Search and switch objects directly from breadcrumbs
- New hierarchy tree navigation:

  - It is now displayed in a dedicated and resizable sidebar on the left.
  - Added pagination on each level with infinite scroll.
  - Highlight current item in view.
  - Improved keyboard navigation and accessibility for easier browsing.
  - Clicking a chevron now expands or collapses the tree without opening the node detail.
  - Clicking a label now opens the node detail without expanding or collapsing the tree.

  When the user arrives directly on the detail view of a hierarchical object:

  - We will show a tree that only display the current node’s parent and siblings for faster loading.
  - Include a ‘Back’ button at the top, to return to the full tree view

#### Fixed

- Prevent long titles from overflowing event cards

  - Long titles now automatically truncate with ellipsis
  - Event cards no longer expand outside the visible area
  - Improves readability and keeps the UI layout intact

  ([#activities-title](https://github.com/opsmill/infrahub/issues/activities-title))
- Display node labels using the following priority: display_label, then hfid, then id. ([#display-labels](https://github.com/opsmill/infrahub/issues/display-labels))
- Backend database sessions are now handled consistently avoiding resource leakage.
- Fix retrieving human friendly ID and display label for relationship nodes via GraphQL, incorrect values could be returned instead of the ones stored in the database
- Fixed a UI issue that prevented the sidebar from fully collapsing when a link existed at the top level.

## [Infrahub - v1.5.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.5.3) - 2025-11-24

### Fixed

- Fixed bug that prevented retrieving cardinality-one relationships on a branch that was already merged and included changes to the relationship.
  This bug would be visible to the user as errors that look like `ValidationError: Too many relationships, max 1 at field_name` ([#7338](https://github.com/opsmill/infrahub/issues/7338))
- Enable caching of the task count in order to avoid performance issues when having a long task history. ([#7568](https://github.com/opsmill/infrahub/issues/7568))
- Refactor task setup to avoid excessive tasks being scheduled for branches that previously didn't contain tasks. The updated behaviour is that the task will only be triggered on the branch if the task signature differs from that of the default branch. ([#7692](https://github.com/opsmill/infrahub/issues/7692))
- Delete branch-aware human friendly ID and display label attributes from branch-agnostic nodes if they were erroneously added. Add branch-agnostic human friendly ID and display label attributes to branch-agnostic nodes and set their values. ([#7694](https://github.com/opsmill/infrahub/issues/7694))

## [Infrahub - v1.5.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.5.2) - 2025-11-17

### Fixed

- Fix migration that backfills display labels and human-friendly IDs to account for schema that only exist on the branch being migrated.
  Add new migration to add display labels and human-friendly IDs to existing instances of templates and profiles. ([#7655](https://github.com/opsmill/infrahub/issues/7655))
- Prevent attempting diff update on a deleted branch. Log a warning instead. ([#7666](https://github.com/opsmill/infrahub/issues/7666))

## [Infrahub - v1.5.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.5.1) - 2025-11-13

### Security

- Updated FastAPI and vulnerable version of starlette

### Fixed

- Disabled scroll on number input fields to prevent accidental value changes. ([#7602](https://github.com/opsmill/infrahub/issues/7602))
- Backend database sessions are now handled consistently avoiding resource leakage.

### Housekeeping

- Bump SDK to fix issue with object file range expansion.

## [Infrahub - v1.5.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.5.0) - 2025-11-10

We're excited to announce the latest version of Infrahub, v1.5.0!

This release delivers major enhancements focused on data lifecycle management, significant performance gains, and operational maturity.

We've made extensive architectural refactors across the board: HFIDs and Profiles are now computed at write time for faster reads, and the display_label property has been modernized to use Jinja2 templating, supporting relationships for richer context.

For automation, we introduced controls to disable generator runs during CI/merge events to eliminate redundancy. We also delivered a crucial new Backup & Restore Tool to orchestrate consistent recovery procedures across Neo4j, PostgreSQL, and artifact storage (initially supporting Docker Compose).

Finally, we've ensured Webhooks are more consistent by aligning custom webhook data formats with standard events, and improved overall efficiency via memory optimizations in multi-branch setups.

## Main changes

### Disable generator in Infrahub's CI pipeline and after a branch merge operation

To provide a cleaner experience when setting up event-based generators, we've introduced the capability to selectively disable generators during specific lifecycle events: CI pipeline execution and branch merge operations.

Previously, generators could be triggered multiple times, leading to redundant processing: once by their configured event trigger rules, again during the Proposed Change (CI) phase, and finally after merging into the main branch.

You can now prevent this overlap by optionally disabling generator execution on a per-generator basis directly within your repository configuration file, `.infrahub.yml`. This ensures your automation runs only when you explicitly intend it to, giving you finer control over when your generation logic executes.

Benefit: Eliminates redundant generator runs

Requirement: This feature requires using version 1.15.0 or newer of the Infrahub Python SDK.

### New Infrahub Backup and Restore tool

We are introducing a new tool to ease the backup and restore process of Infrahub.

Infrahub stores critical state for your infrastructure in multiple systems: the Neo4j graph database, the PostgreSQL database that powers the task manager, and external artifact storage. If any piece is lost or corrupted, you can end up with drifted configurations, orphaned tasks, or a completely unusable deployment. Regulatory requirements and business continuity plans often demand auditable recovery procedures, so "having some dumps around" is rarely enough—you need consistent, verifiable recovery points.

The Infrahub Backup & Restore Tool orchestrates backup and restore workflows across deployment targets. It coordinates quiescing and snapshotting services, pulls data out with the right credentials, and packages everything so restores are deterministic. During restore, the tool brings services back in dependency order, reapplies data, and captures logs so you can prove the operation succeeded.

Installation instructions for the `infrahub-backup` tool can be found in the [documentation](https://infrahub-ops-cli.pages.dev/).

At this stage the tool only support Docker Compose based deployments, in the future we will be adding support for other deployment methods, such as Kubernetes.

### Refactor HFID of objects

We’ve refactored how HFIDs are handled internally to improve performance and scalability.

Previously, HFIDs were computed on-the-fly at read time and were not stored in the database. On objects with many relationships, this could lead to slower queries and higher CPU usage.

With this release, Infrahub now computes the HFID at write time (on create and update) and persists it in the database. Reads no longer need to derive HFIDs dynamically, resulting in faster object retrieval and more predictable query performance.

### Refactor the display_labels of objects

We’ve modernized how object display labels are defined and resolved, adding support for templating and relationships.
Previously, display_labels were evaluated dynamically at read time, which impacted query performance at scale and prevented us from supporting relationships.

What’s new:

- Computed at write time: display_label is now computed on create/update and stored, improving read performance.
- Templating with Jinja2: define display_label using the same Jinja2 syntax available for computed attributes, including first-level relationships.
- Simple single-attribute shorthand remains supported, e.g. `attribute__value`
- For multi-field labels, use Jinja2: `{{ relationship__attribute__value }}-{{ attribute__value }}`

Deprecation and migration:

- The display_labels property is deprecated in favor of display_label.
- Infrahub automatically migrates existing schema nodes:
  - `display_labels: ["name__value"]` → `display_label: name__value`
  - `display_labels: ["type__value", "name__value"]` → `display_label: {{ type__value }} {{ name__value }}`

You can review the result on each schema node’s detail page (Menu > Object Management > Schemas).

⚠ **Required action after migration**:

Update your schema files to use the new `display_label` property and remove deprecated `display_labels` after verifying the automatic migration.

In the documentation you can find specific instructions to migrate existing schema nodes to the new `display_label`: <https://docs.infrahub.app/release-notes/deprecation-guides/display_labels/>

Today, in some places in the UI, we are using the HFID of objects to display them with useful context. This was mostly done to overcome the restriction of not supporting relationships in the `display_label`. In a future release we will use the `display_label` for this instead.

### Refactor profiles

Profiles have been reworked for performance and future flexibility.
Previously, attribute values derived from profiles were resolved dynamically at read time, which could impact performance at scale. With 1.5.0b0:

- Attribute values influenced by profiles are now computed and stored at write time (create/update object or profile).
- Reads no longer have to compute derived values, improving query performance and predictability.
- This refactor lays groundwork to expand profile capabilities, such as adding relationships to profiles in future versions of Infrahub.

### Memory optimizations

We reduced the memory footprint of the GraphQL schema in multi-branch setups:

- Branches that use the exact same schema now share the same in-memory GraphQL schema.
- Individual GraphQL types can be shared across schema versions across branches where compatible.

This lowers memory consumption and improves runtime efficiency.

### Webhook improvements

#### Aligned the format of custom webhooks with the schema of standard webhooks

The format of the event data that custom webhooks receive in a Python transform, is now aligned with the format of events in standard webhooks. This allows users of custom webhooks to have access to the same data as standard webhooks.

An example of the format of the event data:

```python
{
    'data': {
        'kind': 'BuiltinTag',
        'action': 'created',
        'fields': ['name', 'description'],
        'node_id': '1869ad37-fb84-8958-58d8-1746970be2f5',
        'changelog': {
            'node_id': '1869ad37-fb84-8958-58d8-1746970be2f5',
            'node_kind': 'BuiltinTag',
            'attributes': {
                'name': {'kind': 'Text', 'name': 'name', 'value': 'Green', 'properties': {'is_visible': {'name': 'is_visible', 'value': True, 'value_type': 'Boolean', 'value_previous': None, 'value_update_status': 'added'}, 'is_protected': {'name': 'is_protected', 'value': False, 'value_type': 'Boolean', 'value_previous': None, 'value_update_status': 'added'}}, 'value_previous': None, 'value_update_status': 'added'},
                'description': {'kind': 'Text', 'name': 'description', 'value': None, 'properties': {'is_visible': {'name': 'is_visible', 'value': True, 'value_type': 'Boolean', 'value_previous': None, 'value_update_status': 'added'}, 'is_protected': {'name': 'is_protected', 'value': False, 'value_type': 'Boolean', 'value_previous': None, 'value_update_status': 'added'}}, 'value_previous': None, 'value_update_status': 'unchanged'}
            },
            'display_label': 'Green',
            'relationships': {}
        }
    },
    'id': 'fe0172b4-8b69-4597-b0f5-17294de85882',
    'branch': 'main',
    'account_id': '1869ab9e-873b-1908-58d0-1746a8ed315d',
    'occured_at': '2025-09-29 06:33:05.523563+00:00',
    'event': 'infrahub.node.created'
}
```

⚠ !!! ***WARNING** this is a breaking change, existing Python transforms for custom webhooks will need to be adapted to handle this new format.

#### Artifact definition name has been added to the webhook payload for artifact events

For artifact events, the webhook payload now includes the artifact definition name.

Events affected:

- `infrahub.artifact.created`
- `infrahub.artifact.updated`

This makes it easier to interpret artifacts in downstream systems without additional API queries and simplifies integration with configuration deployment frameworks.

### Web interface improvements

- Bulk select objects in list view — select multiple rows to apply bulk actions more efficiently.
- Better navigation for large diffs — improvements to the branch and proposed change diff views help you navigate big changes faster.
- Task list: direct access to related nodes — from each task, you can jump directly to the related nodes for quicker investigation.

### Convert between object types

You can now convert an object from one schema type to another without recreating it. This is especially useful when evolving objects as their type changes—for example, transforming a Layer 2 interface into a Layer 3 interface on a device.

Conversion of object type is available via: GraphQL API, Infrahub Python SDK and the Web interface

To streamline conversions, Infrahub proposes a field mapping that aligns attributes and relationships from the source type to the destination type. You can review and adjust the suggestions and provide values for any fields where no suggestion is available.

The following query has been added to the GraphQL API:

- `FieldsMappingTypeConversion` returns suggested mapping between source and destination types

The following mutations have been added to the GraphQL API:

- `ConvertObjectType` converts an object using the provided mapping

The following methods have been added to the Infrahub Python SDK:

- `convert_object_type` converts an object using the provided mapping

![Convert Object Type](https://github.com/user-attachments/assets/d7d6b0ba-867e-4116-94be-8db4e598495b)

### SDK improvements

Version 1.5.0 of Infrahub requires the usage of infrahub-sdk version v1.15.0, which has been published to [PyPi](https://pypi.org/project/infrahub-sdk/1.15.0b0/).

#### Diff based on timestamp

- `create_diff` — manually create a diff between two timestamps on a branch.
- `get_diff_summary` now accepts start/end timestamps to retrieve that diff.

#### Object type conversion

new `convert_object_type` method — converts an object to a different type using field mappings.

#### Clearing attribute/relationships of objects

You can clear the value of an optional attribute and a cardinality one relationship of an object via the SDK.

#### Support for object file range expansion

Object templates support range expansion on string attributes to generate multiple similar objects more easily (e.g., device interfaces).

## Deprecations

### Graphql mutations

`IPPrefixPoolGetResource` and `IPAddressPoolGetResource` have been deprecated in favor of `InfrahubIPPrefixPoolGetResource` and `InfrahubIPAddressPoolGetResource`. The deprecated mutations will be removed in a future release. Please update your integrations accordingly.

### SDK

In the SDK client the `raise_for_error` attribute has been deprecated for the following methods:

- `execute_graphql`
- `query_gql_query`
- `get_diff_summary`
- `allocate_next_ip_address`
- `allocate_next_ip_prefix`

Migrate to try/except for handling errors raised by these methods. The deprecated attribute will be removed in a future release.

## Full changelog

### Added

- Clean up deadlocks at set intervals controlled by the `INFRAHUB_CACHE_CLEAN_UP_DEADLOCKS_INTERVAL_MINS` environment variable with a default value of `15` mins ([#1290](https://github.com/opsmill/infrahub/issues/1290))
- Generate order_weight for generic templates ([#7157](https://github.com/opsmill/infrahub/issues/7157))
- Added new error message for git connection error ([#7392](https://github.com/opsmill/infrahub/issues/7392))
- - Added a "Select All" checkbox on list views that selects all rows currently loaded on the page.
  - Select multiple rows at once by holding Shift and clicking.
- Add `InfrahubRecomputeComputedAttribute` GraphQL mutation to trigger computed attribute re-computation on all nodes of a given kind or a subset of nodes given their IDs
- Add support for updating existing Profiles when the associated node or generic schema is updated to change an attribute's optional or read-only value or when an attribute is added or removed
- Added a 'warnings' attribute to the API payload for /api/schema/load and /api/schema/check, so that deprecation warnings could be returned for non critical schema violations.
- Added the name of the artifact definition to the payload of artifact webhook events.
- Added warnings to API endpoints /api/schema/check and /api/schema/load, as a way to notify schema developers when they use deprecated fields.
- Allow objects to be converted to another type by mapping fields or defining custom values.

  - For attributes, values from the source object will appear in the target form when the attribute type matches between the source and target schemas.
  - For dropdowns and enums, if the set of options is identical in both schemas, the selected source value will appear in the target form; otherwise, no value will be shown.
  - For relationships, linked objects from the source will appear in the target form when the related object type matches between the source and target schemas.
- Branches list page refreshed:

  - Improved layout for clearer grouping and labels
  - Better accessibility and full keyboard navigation
  - New: branch status is now displayed

  Branch details page:

  - Now shows all branch attributes for a complete view.
  - Added fields: description, status, schema changes, and sync with Git.

### Changed

- Add a new flow to apply migrations inside branches that will also set a `graph_version` property on branches after running. The upgrade process (via the provided command) is also updated with a new `--rebase-branches` flag to trigger branch rebases as part of the upgrade process. Also add the `NEED_UPGRADE_REBASE` branch status to identify branches that need the migrations flow to run.
- Increase default timeout for transform/checks from 10 to 60 seconds

### Fixed

- Prevent creation of relationships with state `absent` ([#4302](https://github.com/opsmill/infrahub/issues/4302))
  - In a proposed change, within the diff tree, clicking the arrow now only expands/collapses the tree without also triggering the item itself (and vice versa).
  - Diff tree and list of changes can be scrolled separately
  ([#5451](https://github.com/opsmill/infrahub/issues/5451))
- Bugfix to allow updating the node kind to null when creating or updating a webhook ([#6397](https://github.com/opsmill/infrahub/issues/6397))
- Breaking change: The format of the data payload has been corrected for transform based webhooks so that they are consistend with standard webhooks as well as custom webhooks (without an attached transform). Due to this change any transforms attached to a webhook needs to be updated to account for the new format. ([#6815](https://github.com/opsmill/infrahub/issues/6815))
- Fixed an issue with resource pools allocating duplicate values on concurrent mutations. ([#7254](https://github.com/opsmill/infrahub/issues/7254))
- Prevent creation of attributes with state `absent` ([#7353](https://github.com/opsmill/infrahub/issues/7353))
- Prevent creation of nodes with state `absent` ([#7354](https://github.com/opsmill/infrahub/issues/7354))
- Fix bug in cypher query that could cause relationships in a large result set to be incorrectly set to null. By default, the nodes in the result set would need to collectively have over 5,000 relationships for the issue to appear.
- Fixed incorrect data diff counter when viewing a branch or proposed changes
- Improved 401 in UI: parallel queries now share a single refresh token call instead of each triggering their own.
- Performance improvements thanks to more granular locking on mutations.
- Resolved a problem that caused generator checks to fail when retrying requests

### Housekeeping

- Pin click version to 8.2.1.
- Refactor Generator execution triggered by an action.

## Migration of an Infrahub instance

Before you upgrade an instance of Infrahub, we strongly advise you to delete branches that are no longer needed within Infrahub. Deleting old branches helps speeding up the upgrade process and to avoid spending time running migrations for branches that are no longer needed.

This process can be used to determine if a branch can be deleted:

- navigate to the branches page in Infrahub
- for each open branch:
  - navigate to the branch detail page
  - refresh the diff from within the data tab
  - review the data and schema changes in the branch
  - if the branch is synchronized with your git repository, review the changes in the files tab
  - review any open proposed changes open for this branch and close or merge the proposed change
  - delete the branch after the proposed changes have been merged/closed or if the changes are no longer relevant

**Please** make sure to upgrade any existing installations of the infrahub-sdk to v1.15.0.

**First**, update the Infrahub version running in your environment.

Below are some example ways to get the latest version of Infrahub in your environment.

- For deployments via Docker Compose, download the updated Docker Compose file
  - `curl https://infrahub.opsmill.io -o docker-compose.yml`
- Set the `VERSION` environment variable and start the environment
  - `export VERSION="1.5.0"; docker compose pull && docker compose up -d`
- For deployments via Kubernetes, utilize the latest version of the Helm chart supplied with this release

**Second**, once you have gotten the desired version of Infrahub in your environment, we need to run migrations because of the changes to the HFID, display label and profiles.

These migrations need to be run on the main branch, and then afterwards the existing branches in Infrahub will need to be rebased, after which the migrations will be run in the branches.

Infrahub provides the `infrahub upgrade` command to start these migrations.

Optionally you can instruct the `infrahub upgrade` command to rebase existing branches and to trigger the migrations on the branches using the `--rebase-branches` option. You can use the `--interactive` option together with the `--rebase-branhces` option. In that case the `infrahub upgrade` command will ask you for each branch, whether you want it to be rebased as part of the upgrade.

Alternatively you can manually rebase branches after you have run the `infrahub upgrade` command. A rebase operation can be performed from the branch detailed view or through the `infrahubctl branch rebase <branch name>` command. The required migrations in a branch will be triggered automatically by Infrahub, after it has been rebased.

Branches that have not been upgraded during the migration, will move to the status `NEED_UPGRADE_REBASE`. In this status you will not be able to merge the branch into main. You will need to rebase the branch before it can be merged.

![NEED_UPGRADE_REBASE](../../media/release_notes/infrahub_1_5_0/release_1_5_need_rebase.jpg)

A rebase operation for a branch can fail, for example when there is a conflict between the branch and the main branch. If the rebase operation for a branch fails, the upgrade command will show an error message with a reason for the failure (if you used the `--rebase-branches` operation).

In that case, the branch will move to the `NEED_UPGRADE_REBASE` status and will need to be rebased manually.
If there was a conflict that prevented the rebase from succeeding, then you will first have to resolve that conflict.

To resolve the conflict, open the branch detailed page and expand the task logs at the bottom. The task log will show you the reason the rebase operation failed.

![Rebase failed console](../../media/release_notes/infrahub_1_5_0/release_1_5_rebase_failed_console.jpg)

![Rebase failed](../../media/release_notes/infrahub_1_5_0/release_1_5_rebase_failed.jpg)

To resolve the conflict, open the data tab and/or the schema tab and inspect the diff.

![Conflict](../../media/release_notes/infrahub_1_5_0/release_1_5_conflict.jpg)

In this image we see a conflict, because Router8 object was renamed in main to Router9 and in the `rename-router` branch the same Router8 object was renamed to Router10. To resolve the conflict we either have to rename the object back to Router8 in main or in the `rename-router` branch.

After resolving the conflict, we can rebase the branch, after which Infrahub will automatically trigger the required migrations.

> Note: If you are running Infrahub in Docker/K8s, this command need to run from a container where Infrahub is installed.

```shell
infrahub upgrade --rebase-branches
```

**Finally**, restart all instances of Infrahub.

### Migration of a dev or demo instance

If you are using the `dev` or `demo` environments, we have provided `invoke` commands to aid in the migration to the latest version.
The below examples provide the `demo` version of the commands, however similar commands can be used for `dev` as well.

```shell
git fetch origin
git checkout infrahub-v1.5.0
git pull
invoke demo.stop
invoke demo.pull
invoke demo.upgrade --rebase-branches
invoke demo.start
```

If you don't want to keep your data, you can start a clean instance with the following command.

> **Warning: All data will be lost, please make sure to backup everything you need before running this command.**

```shell
git fetch origin
git checkout infrahub-v1.5.0
invoke demo.destroy demo.build demo.start demo.load-infra-schema demo.load-infra-data
```

The repository <https://github.com/opsmill/infrahub-demo-edge> has also been updated, it's recommended to pull the latest changes into your fork.

## [Infrahub - v1.4.13](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.13) - 2025-11-06

### Added

- Added new error message for git connection error ([#7392](https://github.com/opsmill/infrahub/issues/7392))

### Changed

- Changed behaviour for when artifacts are regenerated during a proposed change. Infrahub now runs the query through the GraphQL query analyzer to check if it's feasible to use the GraphQLQueryGroup to track all of the members, if this is the case Infrahub can selectively regenerate artifacts on non git integrated branches to avoid regenerating all artifacts. ([#4991](https://github.com/opsmill/infrahub/issues/4991))
- Updated the internal GraphQLQueryAnalyzer to correctly report that queries that require a single unique ID should be reported as having a single response where any future updates would have been captured within a GraphQL query group.

### Fixed

- Fix bug in branch merge logic that could cause duplicate edges to be created to Nodes that had their kind or inheritance updated on the default branch.
  This would have been invisible to the end user until they tried to rebase a new branch onto the default branch, at which point they would have seen errors that mentioned "Relationship-level 'count' constraint violation"
  Also includes a fix to the diff calculation logic to stop including the older versions of nodes with migrated kind or inheritance when it is not actually part of the changes on the branch. ([#7432](https://github.com/opsmill/infrahub/issues/7432))
- Fix bug in cypher query that could cause relationships in a large result set to be incorrectly set to null. By default, the nodes in the result set would need to collectively have over 5,000 relationships for the issue to appear.
- Resolved a problem that caused generator checks to fail when retrying requests

## [Infrahub - v1.4.12](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.12) - 2025-10-23

### Added

- - Schema Visualizer now displays `on_delete` settings for relationships
  - Fixed display of common_parent settings in relationships.

  ([#7431](https://github.com/opsmill/infrahub/issues/7431))

### Fixed

- Loosen requirements for upsert mutations in the GraphQL schema so that required fields can be supplied by a template. ([#7398](https://github.com/opsmill/infrahub/issues/7398))
- Fix a bug that could cause duplicated attributes to be created when updating a generic schema with a new attribute. Includes a migration to fix any existing duplicated attributes created by this bug. ([#7407](https://github.com/opsmill/infrahub/issues/7407))
- Fix bug in logic to create an object from a template that would prevent existing objects in relationships of sub-templates from being correctly linked to the created object. ([#7430](https://github.com/opsmill/infrahub/issues/7430))
- The artifact count has been removed from the Proposed Changes list view.

## [Infrahub - v1.4.11](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.11) - 2025-10-17

### Added

- The login form now automatically focuses on the first field.

### Fixed

- Frontend Updates
  - Consistent font size for all events in the Proposed Change timeline
  - Proposed Change action buttons now keep their size and does not strectch anymore
  - Prevent overflow on the create new relationship button within the relationship input
  - fixed typos

- SSO Fixes ([#6969](https://github.com/opsmill/infrahub/issues/6969))
  - Improved logging for SSO authentication to provide better debugging information
  - Enhanced error handling to properly support all error codes returned by identity providers

- Artifact Display Fixes ([#7294](https://github.com/opsmill/infrahub/issues/7294))
  - Correctly display XML and CSV artifacts in the UI.
  - Added a fallback to plain text for unsupported content types.

- Fix a bug that allowed duplicate attributes and/or relationships on Node or Generic schemas to be merged into the default branch,
  which would cause the application and workers to crash with an error message similar to the following:

  > ValueError: SchemaName: Names of attributes and relationships must be unique : ['field_name_1', 'field_name_2']

  Added a new CLI command `infrahub db check-duplicate-schema-fields` to resolve this duplicated schema fields issue if it appears. ([#7346](https://github.com/opsmill/infrahub/issues/7346))
- Fixed an issue where boolean fields in the object Details view always displayed a checkmark, even when the value was false. ([#7372](https://github.com/opsmill/infrahub/issues/7372))
- Fixed prefix utilization showing as greater than 100% after setting the pool attribute to false ([#7388](https://github.com/opsmill/infrahub/issues/7388))
- Corrected the labels on the branch list and detailed view to use the correct terminology
- Fixed issue with number pool popover stuck in the top-left corner and not expandable during the initial render in some cases.
- Improved artifacts generation and proposed change checks performance by leveraging caching and avoiding excessive GraphQL queries.

## [Infrahub - v1.4.10](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.10) - 2025-10-01

### Fixed

- Fix issue with template that would set the value/source of all attributes even for the attribute that are not defined in the template. ([#7259](https://github.com/opsmill/infrahub/issues/7259))
- Fix bug in artifact diff cypher query that could improperly exclude artifacts on the default branch ([#7301](https://github.com/opsmill/infrahub/issues/7301))

### Housekeeping

- Update docs to download compose file first and then run compose up/down. This change was made due to community members using the one liner for long standing installations without the docker-compose.yml file locally. The new approach is more explicit and easier for the community to maintain their Infrahub instances in the future. ([#compose](https://github.com/opsmill/infrahub/issues/compose))

## [Infrahub - v1.4.9](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.9) - 2025-09-26

### Fixed

- Fix prefix/IP Address creation when passing in `ip_namespace`'s HFID ([#7239](https://github.com/opsmill/infrahub/issues/7239))
- Fix bug in schema integrity checks of a proposed change that prevented resolved violations from being removed ([#7278](https://github.com/opsmill/infrahub/issues/7278))

## [Infrahub - v1.4.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.8) - 2025-09-23

### Fixed

- Report proper branch when read-only repositories fail to synchronize due to invalid branch ([#5713](https://github.com/opsmill/infrahub/issues/5713))
- Add an HFID for Attribute and Relationship matches for a Node Trigger Rule ([#6713](https://github.com/opsmill/infrahub/issues/6713))
- Use the prune flag when fetching updates from remote git repositories to clear deleted remote references locally ([#6884](https://github.com/opsmill/infrahub/issues/6884))
- Fix branch delete query to avoid out-of-memory error when using the community edition ([#7161](https://github.com/opsmill/infrahub/issues/7161))
- Fix bug in GraphQL queries that filter on the ID(s) of peer nodes that could cause nodes to be improperly excluded if the peer's schema had its name, namespace, or inheritance updated. ([#7247](https://github.com/opsmill/infrahub/issues/7247))
- Convert GraphQL query group update tasks to interval to hide it from the task list
- Ensure the default branch is used when a node is part of the global branch
- Update a cypher query that did not correctly account for deleted Relationships. It was only used during a delete, so would not have caused any issues visible to the user.

## [Infrahub - v1.4.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.7) - 2025-09-16

### Added

- Added optional configuration to fetch and map groups when using Google as an identity provider for OAuth/OIDC.
- Added the name of the artifact definition to the payload of artifact webhook events.

### Fixed

- Allow RequestGraphQLQueryGroupUpdate parameters to accept any type of value, not just strings. ([#7208](https://github.com/opsmill/infrahub/issues/7208))
- The available IPs filter in IPAM list views now stays applied when switching kind.

## [Infrahub - v1.4.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.6) - 2025-09-10

### Added

- Make related nodes clickable in task views ([#6420](https://github.com/opsmill/infrahub/issues/6420))
- Add an option to match trigger actions on any attribute value

### Fixed

- Fix bug in IP reconciliation that could cause prefixes or addresses updated on a branch to have incorrect parents or children. ([#6934](https://github.com/opsmill/infrahub/issues/6934))
- Fixed the accepted types for the query payload in the `execute_query` POST endpoint. ([#7119](https://github.com/opsmill/infrahub/issues/7119))
- Fixed issue where the artifact diff view would randomly add space characters to the diff content and highlight it as a diff. ([#6974](https://github.com/opsmill/infrahub/issues/6974))

## [Infrahub - v1.4.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.5) - 2025-09-08

### Security

- Fixes bug in authentication logic that allowed expired and/or deleted API tokens to authenticate successfully.

### Fixed

- Fixed an issue where switching between relationships to the same schema didn’t refresh the table correctly. ([#6418](https://github.com/opsmill/infrahub/issues/6418))
- Add initialization instructions for Infrahub repository to docs. ([#7137](https://github.com/opsmill/infrahub/issues/7137))
- Relationship properties now show a clearer loading indicator.
- Standardize internal cache-key generation using factories to make request handling easier and more consistent.
- Fixed a bug in the object table where the kind selector was not filtering its options correctly.

### Housekeeping

- Internal(frontend): Upgraded Biome to v2. Now use Ultracite to configure Biome
- Internal(frontend): Cleaned up unused files and functions

## [Infrahub - v1.4.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.4) - 2025-09-03

### Fixed

- Fix HTTP 403 when trying to fetch object metadata in changelog without being allowed to manage permissions ([#ifc1760](https://github.com/opsmill/infrahub/issues/ifc1760))
- Fix HTTP 403 when trying to fetch nodes though a `CoreNode` query, this could prevent users to select nodes in various places with the user interface ([#6733](https://github.com/opsmill/infrahub/issues/6733))
- Re-run Migration026 in case it failed during an upgrade from 1.2.4 or earlier to 1.4.x or later. Root cause of the migration failure has already been addressed. ([#7112](https://github.com/opsmill/infrahub/issues/7112))
- Fixed rebase bug by ensuring rebase operations with data only changes correctly set the .branched_from property of the branch within the registry. ([#7113](https://github.com/opsmill/infrahub/issues/7113))
- UI requests for proposed change objects are now branch-agnostic, preventing errors when a branch is deleted

### Housekeeping

- Internal UI: Decouple config fetching from usage

## [Infrahub - v1.4.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.3) - 2025-08-29

### Fixed

- Force branches data to be reloaded when the hash doesn't look healthy
- In the UI, clicking the artifact generation button now refreshes the token and retries if the access token has expired.

## [Infrahub - v1.4.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.2) - 2025-08-28

### Fixed

- Fix a bug where a proposed change could be merged without approval even if some approvals were required (Enterprise)
- Removed incorrect log warning about 'Branch schema hash is not set, cannot update branch registry' due to including the '-global-' branch when processing branch updates.

## [Infrahub - v1.4.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.1) - 2025-08-27

### Fixed

- Fix bug in schema validation that would incorrectly flag Dropdown attributes of node schema that override a generic attribute as having illegal values ([#7086](https://github.com/opsmill/infrahub/issues/7086))

## [Infrahub - v1.4.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.4.0) - 2025-08-26

We're excited to announce the first release candidate of Infrahub 1.4.0!

This release focuses on several key improvements to enhance usability, performance, and enterprise-level control.

The most significant update is the redesign of the generic list view, which now dynamically adapts columns and filters based on the selected schema node. This change underpins major improvements to the IPAM module, including better contextual information, performance boosts, and new features like displaying and creating objects from available address space.

For our Enterprise customers, we've introduced a proposed change approval workflow, allowing teams to implement proper change control with configurable approval settings and improved visibility into change status.

Additionally, this release introduces bulk edit capabilities in the object list view. We've also added signing and authentication for custom webhooks and implemented several performance improvements across the application, including the re-enabling of attribute indexes.

### Main changes

#### UI generic list view allows you to select a specific schema node

The list view of generic schema nodes, now contains a dropdown control that allows you to select a specific schema node that inherits from this generic. When selecting a specific schema node, the list view will be filtered to the objects of that kind and the columns in the list view will now show you the attributes and relationships of that kind.

If there's only 1 specific schema node inheriting from the generic, then it will be automatically selected and the list view will immediately show the attributes and relationships of this schema node.

#### IPAM improvements

Several improvements have been made to the IPAM functionality in Infrahub, improving the overall experience when navigating IPAM data or when searching for new available IP address space.

##### Improved contextual information on prefixes and addresses

The IPAM views have been updated to leverage the [generic list view improvements](#UI generic list view allows you to select a specific schema node). Schema nodes inheriting from the BuiltinIPPrefix or BuiltinIPAddress generics will now show additional attributes and relationships that are defined on them, providing more context when navigating the IPAM tree.

##### Hide tree navigation component

You can now hide the IPAM tree navigation component, providing more space to display the information in the IP prefix and IP address list views.

##### Display available prefix or address space

Infrahub can now optionally display available IP prefixes or IP addresses in the IPAM view.

For prefixes, Infrahub will automatically calculate the largest available prefixes it can create and display them in the interface.
Similarly Infrahub will calculate the available IP addresses, summarizing them into ranges when possible.

##### Create new IP Prefix or IP Address objects from available prefix or address space

Clicking an available IP Prefix or IP Address in the list view of Infrahub, will now open the object creation form, which will be prefilled with the available IP prefix or IP address, simplifying the process of creating new IP Address or IP Prefix records.

##### Improved default view

When you click on an IP Prefix object in the IP prefix list view, Infrahub will now show you the child prefixes or the IP addresses contained within that prefix. What data is being displayed depends on the member type defined on the prefix object.
Additionally more detailed information about the prefix will be available in that view.

##### Performance improvements

Performance improvements have been made to improve the overall user experience while navigating your IPAM data in Infrahub.

##### Ability to create new IP prefixes and IP addresses using resource managers

The frontend now supports creating new IP prefix and IP address objects using resource managers, previously this was only possible on nodes that had a relation to an IP address or IP prefix object.

#### Proposed change approval workflow (Enterprise)

Add support to configure required approvals of proposed changes, allowing users to implement proper change control mechanisms.

- a new global permission has been introduced to allow users to review a proposed change
- configuration setting that allows you to define a required amount of approvals (enterprise only)
- configuration setting to automatically revoke approvals when new changes are made to a branch (enterprise only)

With this change multiple improvements have been made to the overall proposed change feature in Infrahub:

- The proposed change list view has been updated, so that you can more easily identify the proposed changes that need your attention.
- Added the ability to set a proposed change to be a draft, allowing you to more easily indicate the state of a certain change
- The overview tab of a proposed change now contains a more detailed timeline of all the actions/state changes that happened in a proposed change.

Please refer to the documentation for a guide that explains how to setup a change approval workflow: <https://develop.infrahub.pages.dev/guides/change-approval-workflow>

#### Bulk edit capabilities

Infrahub now supports bulk edit capabilities in the object list view in the web interface, allowing you to modify attributes/relationships of multiple nodes in a single operation.

#### Custom webhooks now support signing and authentication using a shared key

Infrahub now supports authentication and signing for custom webhooks. Previously this was only possible for standard webhooks.

#### Performance improvements

Several improvements were made to improve the performance of Infrahub.

- Re-enable attribute indexes at the database level
- Support scaling out the prefect task manager component (enterprise) (experimental)

### Full Changelog

#### Added

- Add support for nested named GraphQL fragments for cardinality=many relationships. ([#5322](https://github.com/opsmill/infrahub/issues/5322))
- Added support for authentication / signing to custom webhooks. If using a transform it is assumed that the transform renders JSON data. ([#6521](https://github.com/opsmill/infrahub/issues/6521))
- Enhance form context to auto-fill parent fields based on the current view. When a user is viewing a node, adding certain relationships will automatically populate parent fields in the form using information from the current node, if available. ([#6686](https://github.com/opsmill/infrahub/issues/6686))
- Make created_by relationship of CoreProposedChange read-only. Set the relationship server-side during the CoreProposedChangeCreate mutation.
- Add `CoreProposedChangeAvailableActions` GraphQL query to get possible actions that can be taken by someone on a proposed change
- Add a permission to allow users to review proposed changes (identifier `global:review_proposed_change:allow_all`). Users with existing Infrahub instances may need to create this permission to use it.
- Add events for proposed change reviews and merge
- Add support to see available IP spaces when querying for generic IP prefixes or generic IP addresses by using the `include_available` filter
- Added new database-level indexing logic to improve performance of queries that are searching for specific values
- New on IPAM:
  - IP Prefix details page now shows the list of members first instead of full details.
  - When viewing a prefix's children list, you can now see the available sub-prefixes.
- On generic list view and IPAM, we added a new picker to select an inheriting schema. When you pick one:
  - The list view updates to display all columns defined by that schema.
  - Filtering and sorting are supported on these schema-specific fields.
  - If the generic schema has only one inheriting schema, the list view will automatically display its columns without requiring manual selection.
- You can now bulk edit selected rows in object list view

#### Changed

- - Enhance the Proposed Changes list view by adding filters and improving the UI.
  - Enhance actions and add a select menu to choose which action to trigger.
  - Allow draft states for proposed changes
  - Add events in main overview page for approvals, rejects and threads
  ([#proposed-changes](https://github.com/opsmill/infrahub/issues/proposed-changes))
- Allow `prefix_length` to be omitted when using `IPPrefixGetNextAvailable` GraphQL query to return the first next available prefix
- Deprecate `IPAddressGetNextAvailable` and `IPPrefixGetNextAvailable` in favour of `InfrahubIPAddressGetNextAvailable` and `InfrahubIPPrefixGetNextAvailable` respectively. Also deprecate mutations `IPPrefixPoolGetResource` and `IPAddressPoolGetResource` in favour of `IPPrefixPoolGetResource` and `InfrahubIPAddressPoolGetResource`.
- Stopped the IPAM menu item from showing up if there are no nodes inheriting from BuiltinIPAddress or BuiltinIPPrefix

#### Fixed

- Raise error on schema load if someone tries to override the peer of a generic relationship as the GraphQL schema doesn't allow for that. ([#6699](https://github.com/opsmill/infrahub/issues/6699))
- Fix bug that prevented proposed changes in the `merging` state from showing in the UI. ([#6749](https://github.com/opsmill/infrahub/issues/6749))
- Fix: Always show suggested filters
- Fixed RelationshipAdd and RelationshipRemove mutations so they can't update read-only relationships
- Fixed an issue where false was shown as `-` instead of `false` in object table

## [Infrahub - v1.3.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.8) - 2025-08-26

### Fixed

- Fixed bugs that would prevent generating a diff for and merging a branch with new schema and data into a fresh instance of Infrahub. ([#6484](https://github.com/opsmill/infrahub/issues/6484))
- Fixed overflow issues with large numbers of tabs on object details view ([#6734](https://github.com/opsmill/infrahub/issues/6734))
- Allow updating mandatory attribute on a generic to being optional, even if the generic is overridden by inheriting schema(s). ([#6800](https://github.com/opsmill/infrahub/issues/6800))
- Add graphiql workers at build time for offline use ([#7046](https://github.com/opsmill/infrahub/issues/7046))

## [Infrahub - v1.3.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.7) - 2025-08-14

### Fixed

- Ensure that only users with "manage schema" permissions can add or remove dropdown and enum values ([#6410](https://github.com/opsmill/infrahub/issues/6410))
- Fix bug in branch delete cypher query that could leave behind orphaned branch-agnostic relationships. Includes a migration to clean up these orphaned relationships. ([#6933](https://github.com/opsmill/infrahub/issues/6933))
- Fix bug in display label rendering that prevented schemas from defining display labels with the same attribute names in different ways (`name` vs `name__value`, for example) ([#7022](https://github.com/opsmill/infrahub/issues/7022))
- Fix resource pool allocation on concurrent mutations. Assignments from the resource pools are now done within a lock to prevent invalid assignments that might occur during concurrent requests.

## [Infrahub - v1.3.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.6) - 2025-08-11

### Added

- Add the `infrahub db check-inheritance` command to validate and fix any schemas that have had their inheritance updated and a failed migration.

### Changed

- Improve performance of node creation, for nodes with a high number of relationships ([#6883](https://github.com/opsmill/infrahub/pull/6883))

## [Infrahub - v1.3.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.5) - 2025-08-05

### Added

- Add a new check for orphaned Relationship vertices to `infrahub db check`

### Fixed

- Fix repository objects view when there is no group tied to the repository [repository-objects](https://github.com/opsmill/infrahub/issues/repo-objects)
- Prevent Python keywords from being used as attribute/relationship names in schemas. Schema validation now rejects Python keywords (like `from`, `class`, `import`) as attribute or relationship names, preventing 500 errors during GraphQL schema generation. ([#6730](https://github.com/opsmill/infrahub/issues/6730))
- Fix bug in diff calculation logic that could prevent the diff from generating if the peer of a deleted node had its kind or inheritance changed on multiple branches ([#6928](https://github.com/opsmill/infrahub/issues/6928))
- Fix an issue in a cypher query to get the peers of a node that has been migrated for a kind or inheritance update.
- Fix an issue in the diff calculation that could double count properties of a node that has been migrated for a kind or inheritance update.

## [Infrahub - v1.3.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.4) - 2025-07-22

### Fixed

- Add migration for Attribute of kind NumberPool on existing nodes ([#6802](https://github.com/opsmill/infrahub/issues/6802))
- Fix an issue where number pools defined on a generic schema attribute couldn’t be used in attributes of inheriting nodes ([#6817](https://github.com/opsmill/infrahub/issues/6817))
- Fix a validation bug that incorrectly blocked form submission when a number pool was selected on an number attribute ([#6817](https://github.com/opsmill/infrahub/issues/6817))
- Fix bug that would cause diff generation to fail if schema for a deleted Node was deleted on both source and target branches ([#6830](https://github.com/opsmill/infrahub/issues/6830))
- Fix 500 error when list of schemas is empty. ([#6834](https://github.com/opsmill/infrahub/issues/6834))
- Ensure Templates attributes and relationships order weights are aligned with original node. ([#6838](https://github.com/opsmill/infrahub/issues/6838))
- Ensure Search Anywhere remains stable during template searches ([#6845](https://github.com/opsmill/infrahub/issues/6845))
- Fix bug that could leave orphaned SchemaRelationships with no linked SchemaNode in the database. These would be invisible to the user until the user tried to merge a branch that included schema changes, at which point they might receive errors that look like this during the schema integrity checks, "Relationship-level 'count' constraint violation on schema 'SchemaRelationship'. Node (SchemaRelationship: 1809b4d6-6838-880b-3408-c51daf04ecbe) is not compliant." ([#6852](https://github.com/opsmill/infrahub/issues/6852))
- Fix Resource Pool utilization query for large IPv6 prefix resource ([#6855](https://github.com/opsmill/infrahub/issues/6855))
- Fix Object template wasn't sent on creation if no fields used template values ([#6859](https://github.com/opsmill/infrahub/issues/6859))
- Fix number allocation for Number Pool to ensure that values that are not used anymore will get back into the pool ([#6865](https://github.com/opsmill/infrahub/issues/6865))
- Fix broken auto-completion in GraphiQL 5 + Vite

## [Infrahub - v1.3.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.3) - 2025-07-15

### Added

- <!-- vale off -->
  Added the `infrahub db check` command to look for illegal data in the database
  <!-- vale on -->
- Add a command to run a single migration
- Updated GraphQL sandbox to GraphiQL 5

### Fixed

- Fix upsert mutation for webhooks ([#6641](https://github.com/opsmill/infrahub/issues/6641))
- Prevent a merge operation and a diff update from running at the same time on the same branch ([#6704](https://github.com/opsmill/infrahub/issues/6704))
- Fix branch delete logic to handle very large branches (millions of edges) and add a migration to clean up any partially deleted branches ([#6797](https://github.com/opsmill/infrahub/issues/6797))
- Explicitly expose port 7687 for Neo4j to ensure the integration tests are running on all setup
- Fix a bug in node creating that could cause duplicate relationships if the node being created included a relationship to a node of a schema that had its kind or inheritance updated in the past
- Fix an issue where prefixes could not be allocated from a pool when passing `member_type` inside the data parameter
- Migration to clean up duplicated relationships

## [Infrahub - v1.3.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.2) - 2025-06-30

### Fixed

- Improve performance of uniqueness constraint checks during create/update/upsert mutations by allowing ordering elements from more specific to less specific within a constraint group ([#6377](https://github.com/opsmill/infrahub/issues/6377))
- Fixed: min/max constraints no longer trigger on empty values when the field is optional. ([#6671](https://github.com/opsmill/infrahub/issues/6671))
- Object template ([#6724](https://github.com/opsmill/infrahub/issues/6724))
  - Fixed "Kind" filter in object template list view.
  - Fixed search in object template selector during creation form
- Improve performance when calculating a large diff with many added and/or deleted node (>2,000) ([#6751](https://github.com/opsmill/infrahub/issues/6751))

## [Infrahub - v1.3.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.1) - 2025-06-27

### Fixed

- Fix bug that could prevent renaming a unique attribute on a schema ([#6147](https://github.com/opsmill/infrahub/issues/6147))
- Fix a bug where Number attribute min_value/max_value/excluded_values constraints were not enforced during node creation ([#6714](https://github.com/opsmill/infrahub/issues/6714))
- Display parameters for attribute of kind `Number` in Schema visualizer. ([#6715](https://github.com/opsmill/infrahub/issues/6715))

## [Infrahub - v1.3.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.3.0) - 2025-06-12

We're excited to announce the release of Infrahub 1.3.0!

This version brings powerful new features designed to streamline your operations and enhance control of your data, as well as new automation possibilities. Our focus for this release is empowering you with greater flexibility and efficiency in managing your infrastructure data.

### Key Highlights

#### Action System

Infrahub 1.3.0 unveils a brand new Action System that lets you automate routine tasks based on system events. Define triggers to automatically add or remove nodes from groups, or even run generator definitions, bringing a new level of dynamism to your infrastructure management.

We will add additional actions in future releases.

#### Load Data from Git Repositories

Infrahub can now automatically load data from object YAML files stored in an external Git repository. This new capability streamlines data ingestion, allowing you to manage your infrastructure data in version control, and Infrahub will keep itself updated. This is similar to how you would import data using object files using the `infrahubctl object load` command.

#### Load menu files from Git Repositories

Expanding on our Git integration, Infrahub can now also automatically load menu configuration files from external Git repositories.

#### Add Parameters as a New Schema Option for Attribute Kinds

Gain finer control over your attribute values with the introduction of attribute parameters. This allows you to define more precise constraints for attribute kinds like Text, TextArea, Number, and the new NumberPool, such as setting minimum/maximum lengths for text attributes or minimum/maximum values for number attributes.

With the release of this feature the `min_length` and `max_length` option for attributes has been deprecated and will be phased out in a future release.

#### Added NumberPool Attribute Kind

A new NumberPool attribute kind has been added, providing a way to dynamically assign a number to the attribute from an automatically created NumberPool. This read-only and mandatory attribute ensures unique and controlled numbering for your critical data.

#### Bulk operations

The Infrahub frontend now supports bulk operations, allowing you to manage large datasets more efficiently and actions on multiple items simultaneously. These bulk operations have been added:

- bulk deletion of objects
- manage group membership of multiple objects

#### IPAM UI

We've made significant improvements to the IPAM user interface, including updating it to use our standard table component and implementing various performance enhancements. This results in a more consistent and faster experience when managing your IP addresses and prefixes.

#### Same parent constraint for relationships

You can now define a Same Parent Constraint on a relationship of a node. This powerful new feature enforces that any node you want to add to a relationship must have a relationship to the same parent as the node to which you are adding the relationship. A common example would be a LAG interface on a device. You would want to make sure that the member interfaces that you can add to the LAG interface are interfaces on the same device.

#### Upgrades for Neo4j

We've upgraded our Neo4j support to version 2025.03.0, ensuring Infrahub leverages the latest advancements for improved performance and reliability.

### Changelog

The complete list of changes can always be found in the CHANGELOG.md file in the Infrahub Git repository.

#### Added

- On object list views, the number of objects now changes when you apply filters in list views. ([#object-count](https://github.com/opsmill/infrahub/issues/object-count))
- Add bulk delete for objects and relationships
  Improve object list loader ([#2932](https://github.com/opsmill/infrahub/issues/2932))
- Add `parameters` field with support for min, max and excluded values for Number attributes. ([#2967](https://github.com/opsmill/infrahub/issues/2967))
- Add `common_parent` relationship list property to be able to enforce nodes to have the same set of peers for each of the listed relationship names. For example, in a schema composed of `Device`, `Interface` and `LinkAggregationInterface`nodes, a relationship named `members` for LAGs that makes sure that all the interfaces in a LAG belong to the same device can be defined like this:

  ```yaml
  - name: members
    peer: ExampleInterface
    kind: Component
    cardinality: many
    optional: true
    common_parent:
      - device
  ```

  ([#3709](https://github.com/opsmill/infrahub/issues/3709))
- Add new parameters field with support for regular expressions, minimum length, and maximum length to Text and TextArea attributes. ([#4246](https://github.com/opsmill/infrahub/issues/4246))
- On artifact details page, added a link "Raw" to open raw artifact file in a new tab. ([#6513](https://github.com/opsmill/infrahub/issues/6513))
- Display repository objects in a dedicated tab ([#6598](https://github.com/opsmill/infrahub/issues/6598))
- Added an event system that lets you setup trigger rules to match against events within the system and fire actions when these events occur. With this feature in place you can automatically add or remove members to groups, or execute a generator.
- Improved the design and accessibility of the menu in the object view
- We added row selection functionality to the table view. Users can now select multiple rows then:
  - add them to groups via the new "Add to groups" button.
  - remove them from groups via the new "Remove from groups" button.
  - delete them via the "Delete" button
  - dissociate selected rows on relationship list view via the new "Dissociate" button.

#### Changed

- Updated IPAM UI components to use standard UI components

#### Fixed

- Allow for missing optional relationships for computed attributes ([#6426](https://github.com/opsmill/infrahub/issues/6426))
- Added missing branch info to group events ([#6435](https://github.com/opsmill/infrahub/issues/6435))
- Resolved performance issue in the IPAM view
- Resolved an issue where the copy to clipboard did not work on insecure (HTTP) URLs. ([#6467](https://github.com/opsmill/infrahub/issues/6467))
- Ensure GraphQL schema is refreshed after a branch rebase ([#6561](https://github.com/opsmill/infrahub/issues/6561))
- Fixed an error preventing pool selection from being listed when peer has a custom namespace
- Hide pool selection on relationship of cardinality many (it'll be added later) ([#6581](https://github.com/opsmill/infrahub/issues/6581))
- Fixed a performance issue with the hierarchical tree view causing long load times, due to over fetching of data

## [Infrahub - v1.2.12](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.12) - 2025-06-03

### Fixed

- Remove uniqueness constraint on generic templates to support upsert mutations ([#6478](https://github.com/opsmill/infrahub/issues/6478))
- Add a migration to clean up duplicated data from improper merges of branches containing node schemas with an updated kind or inheritance ([#6502](https://github.com/opsmill/infrahub/issues/6502))
- Update the cypher query that saves a diff to use less memory. ([#6568](https://github.com/opsmill/infrahub/issues/6568))
- Add missing database session instantiations
- Display generic relationships with cardinality one in the object detail view.
- Fixes schema migration to add new attributes, so that it no longer adds that attribute to nodes that have been deleted. Includes a migration to clean up those illegal edges.

## [Infrahub - v1.2.11](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.11) - 2025-05-23

### Added

- Add the `CoreWeightedPoolResource` generic to better control which resource should be used when allocating from a pool. The higher the weight of the resource, the more likely it is to be selected for allocation.

### Changed

- The scrollbar in the infinite scroll tables, is now only visible when your mouse hovers the table.

### Fixed

- Fix a problem in the logic to calculate a diff that could cause it to quit too early under certain unlikely circumstances
- Fixes an issue where the next page of data was loaded even when the infinite scroll table wasn't scrolled.

## [Infrahub - v1.2.10](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.10) - 2025-05-13

### Added
<!-- vale off -->
- Added the ability to use alternative value types for all attribute types with computed attributes. For attributes of type IPHost or Dropdown you can now access the `ip` or `label` fields and not only the `value` field. ([#5769](https://github.com/opsmill/infrahub/issues/5769))
- Computed Attribute of kind Jinja will only be recalculated during a schema update if the template itself has been updated.
<!-- vale on -->

### Fixed

- Fixes an issue where the signature of a webhook event was calculated wrongly. ([#6323](https://github.com/opsmill/infrahub/issues/6323))
- Display "dissociate" action only if possible on relationships table's row actions
- Fixed an issue where it wasn't possible to have a high number of choices in the Dropdown schema kinds. Previously the payload was limited to 4096 characters.
- Prevent creating duplicate edges on the database when adding a relationship to or deleting a relationship from a node that had its kind or inheritance updated
- Update diff and merge logic to correctly support nodes that have had their kind migrated on a branch

## [Infrahub - v1.2.9](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.9) - 2025-05-07

### Added

- Added the `INFRAHUB_TESTING_SCHEMA_STRICT_MODE` environment variable to allow users to control `INFRAHUB_SCHEMA_STRICT_MODE` when using `infrahub-testcontainers`.
- Improved the performance of the core database class used throughout the backend by factoring out the classes used for creating and removing indexes.

### Changed

- Sped up computed attribute mutation by changing the node query to only request the required attributes from the database. This change will provide performance improvements for the background processing of computed attributes. ([#6403](https://github.com/opsmill/infrahub/issues/6403))

### Fixed

- Deleting a branch now correctly deletes nodes with agnostic relationships. This typically fixes an issue after deleting a branch where an object had been created on this branch through a ResourceManager ([#5463](https://github.com/opsmill/infrahub/issues/5463))
- Fixed `textarea` values display in the object details view. ([#6400](https://github.com/opsmill/infrahub/issues/6400))
- Added inherited kinds of a node as templates to fix GraphQL schema when inheritance is involved. ([#6415](https://github.com/opsmill/infrahub/issues/6415))
- Fixed an issue with computed attribute that would trigger multiple updates after a schema change if the attribute reference multiple kind of nodes.
- Updated the date formatting to include the year for dates before the current year, and ensure consistency between the list and detail views.

## [Infrahub - v1.2.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.2.8) - 2025-05-01

### Added

- Added support for "convert_query_response" for Python transforms. The feature works the same was as with Generators. Note any non default branch will need to be rebased after this upgrade. ([#6383](https://github.com/opsmill/infrahub/issues/6383))
- Enabled HCL syntax highlighting for artifacts.

### Fixed

- Improved performance when retrieving nodes that have thousands of relationships.
- Improved performance of the Git credential helper.

### Housekeeping

- Background performance improvements due to Prefect 3.3.7 upgrade.

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
