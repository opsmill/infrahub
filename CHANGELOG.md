# Infrahub changelog

This is the changelog for Infrahub.
All notable changes to this project will be documented in this file.

Issue tracking is located in [GitHub](https://github.com/opsmill/infrahub/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/infrahub/tree/develop/infrahub/changelog/>.

<!-- towncrier release notes start -->

## [Infrahub - v1.12.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.12.0) - 2026-11-10

Infrahub 1.12 focuses on how Infrahub works with your Git repositories. Before you merge an Infrahub branch, you can check which commit it imported from each repository and whether the import succeeded. If Infrahub cannot push a merge back to Git, you can view the cause and retry. The release also changes how number pools allocate numbers, reduces the processing after large merges, adds tracing for slow automation, and introduces dark mode as an alpha.

This release contains breaking changes that need action before you upgrade. See [Before you upgrade](#before-you-upgrade).

### Release highlights

- **[Review changes to automation and data together with greater confidence](#review-and-troubleshoot-git-repository-changes).** Verify that schemas, templates, Transformations, and Generator definitions have been imported successfully from Git before merging an Infrahub branch. If synchronization fails, you can identify the cause and recover while continuing to test changes on other branches.
- **[Automate on the infrastructure you already operate](#allocate-new-numbers-while-preserving-existing-assignments).** Record the numbers your objects already hold in a number pool and allocate new numbers alongside them. A pool can now contain multiple ranges and keep a separate allocation sequence for each site or other scope.
- **[Keep making changes efficiently as your infrastructure grows](#merge-and-review-large-changes-with-fewer-delays).** Reduce the processing required to update computed attributes and validate large Proposed Changes, and [trace slow Generators, Transformations, and API requests](#diagnose-api-response-times-and-automation-delays) to identify where time is spent.
- **[Work in dark mode (alpha)](#announcing-dark-mode).** Choose a dark appearance or match your operating system's theme.

### Before you upgrade

Review the [breaking changes and required actions](#breaking-changes-and-required-actions), particularly if you use any of the following:

| If you use… | Preparation |
|---|---|
| Generators that manage objects | Before upgrading, update each Generator to save every object it must retain on every run, including unchanged objects. |
| Git repositories that define objects | Before upgrading, restore any removed object files and their `objects:` entries if you want to retain those objects in Infrahub. |
| SSO with existing accounts | Link existing accounts to their SSO identities before the account-name fallback default changes. |
| Experimental NATS drivers | Before upgrading, replace the NATS message broker with RabbitMQ and the NATS cache with Redis. |
| Number pools for unique attributes | Before allocating numbers after upgrading, record existing assignments in their pools and resolve overlapping pool ranges. |
| Local `infrahubctl` commands | Before running Generators, Transformations, or checks after upgrading, select the intended Infrahub branch explicitly or enable selection from your current Git branch. |

### Announcing Dark Mode

You can now work in Infrahub in dark mode or match your operating system's appearance. The [**Theme** menu](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/faq/faq.mdx#does-the-web-interface-have-a-dark-theme) in your account offers **Dark**, **Light**, and **System**. Dark mode is available as an alpha; some pages may still display incorrect colors.

### Review and troubleshoot Git repository changes

Before merging an Infrahub branch, you can now confirm that it successfully imported the intended changes to schemas, templates, and automation definitions stored in a connected Git repository. If the merge completes in Infrahub but updating Git fails, you can also resolve that error without repeating the Infrahub merge.

- **Resolve repository import errors before merging.** Compare [the imported commit and import status](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/git-integration/branch-synchronization.mdx#checking-a-repositorys-status-on-every-branch) across Infrahub branches on the repository page. When reviewing a Proposed Change, failed or incomplete imports now appear in its checks, with the affected repository and correction needed. A merge fails until [required imports succeed](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/branches/merge.mdx#before-the-merge-starts-repository-imports).
- **Complete the Git update after an Infrahub merge.** You can now inspect why the connected Git repository could not be updated and [retry after correcting the cause](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/git-integration/branch-synchronization.mdx#retry-the-pending-pushes). Alternatively, abandon the Git update while keeping the completed Infrahub merge. Temporary failures are retried automatically.
- **Review new Git commits before importing them into Infrahub.** For read-only repositories, automatic checks make new commits available to review in the [**Commits** tab](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/git-integration/overview.mdx#commits-tab). Choose when to import them; until then, Infrahub uses the previously imported version.
- **Continue working on other branches while correcting an import error.** Errors in one Git branch's schema, object data files, or GraphQL queries no longer stop imports from other Git branches.
- **Continue using a Git branch after rebasing it.** Rebased or force-pushed branches in connected read-write repositories now import without the false merge conflicts that previously interrupted synchronization.

### Allocate new numbers while preserving existing assignments

Allocate numbers to objects alongside the numbers already in use in your infrastructure. You can now [record existing assignments in a number pool](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/track-existing-numbers.mdx) without changing their values. The pool marks those numbers as used and excludes them when allocating new ones.

- **Assign a specific number from a pool.** You can now [choose the number an object receives](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/allocate-number.mdx#request-a-specific-number) instead of taking the next available number. The pool records the assignment and excludes that number from subsequent allocations.
- **Allocate around gaps in your numbering plan.** A pool can now contain [multiple ranges](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/allocate-number.mdx#change-the-ranges-of-a-pool), such as 100–199 and 300–399, leaving 200–299 outside automatic allocation. You can also choose which range the pool uses first.
- **Reuse the same numbers across sites or other scopes from one pool.** [Allocation scopes](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/allocate-numbers-per-scope.mdx) let one pool keep a separate allocation sequence for each value of an attribute or relationship you choose, such as the site an object belongs to. The pool can assign the same number to objects at different sites without allocating it twice within one site.
- **Identify where more numbers are needed.** You can now [check how much of each range or allocation scope is in use](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/allocate-number.mdx#view-how-much-of-a-pool-is-in-use) to decide where to expand a pool. You can also view which object holds each number and on which branch.

### Merge and review large changes with fewer delays

When you change data across a large infrastructure, you can review and merge your changes with fewer delays from recalculating computed attributes and running checks.

- **Get updated computed attribute values sooner after a merge or rebase.** Merges and rebases now recalculate each affected [Python computed attribute](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/computed-attributes/overview.mdx#python-computed-attribute) in batches of objects, instead of starting one task for every changed object. In a test merge of an AI data center fabric with 1,504 interfaces, this took 7 tasks instead of 1,504 on Infrahub 1.11.3, so the values are up to date sooner when you generate artifacts or run Generators. This applies when the attribute's Transformation uses a [query that targets a single object](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/development-resources/graphql/single-target-queries.mdx). Otherwise, Infrahub recalculates the attribute for every object of its kind.
- **Check requirements across large groups of objects with fewer API requests.** Before merging a Proposed Change, you can [check requirements](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/checks/overview.mdx), such as naming conventions, across the objects in your target groups. Previously, the API load of these checks grew with the square of the number of objects in the group. Artifact checks receive the same improvement. Proposed Changes with many checks also finish validation sooner, because Infrahub now reads the state of all running checks together instead of one at a time.
- **Complete artifact checks for large groups of objects.** The CI pipeline of a Proposed Change [generates the artifacts from your branch](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/proposed-changes/overview.mdx#artifact-generation), so you can compare them before merging. For artifact definitions that target about a thousand objects, these artifact checks no longer stay in progress after a connection pool timeout, which blocked the merge.
- **Edit one automation definition without rerunning the others.** When you [change an artifact or Generator definition in `.infrahub.yml`](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/proposed-changes/overview.mdx#understanding-artifact-regeneration), Infrahub now regenerates the artifacts or runs the Generator for that definition only. An edit that changes no definition, such as a comment, regenerates nothing. A definition that still regenerates on any repository file change, or that lists `.infrahub.yml` under `watch.files`, runs on every edit.

### Diagnose API response times and automation delays

When an API request takes longer than expected to return, or a Generator or Transformation takes longer to complete, you can now trace the operation to its database queries and check for waits on task workers or database connections.

- **Find the query behind a slow task.** [Enable tracing](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/run-observe/own-monitoring.mdx) and follow a Generator or Transformation through its API calls to the database queries in one connected trace. Identify which query accounts for the delay and inspect the related process logs.
- **Investigate capacity constraints and slow queries.** You can now see how long tasks wait to start and how long queries wait for database connections, alongside running tasks and connection usage. Use this information to investigate whether work is waiting for capacity or taking longer to execute, through the [supplied Grafana panels](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/run-observe/metrics.mdx) or dashboards you configure in your own monitoring system.
- **Capture intermittent problems without restarting.** With tracing enabled, administrators with `super_admin` permission can now [temporarily record more traces](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/install-configure/install/observability-stack.mdx#record-more-traces-during-an-incident) while an incident is happening. Set a duration of up to 24 hours; trace collection then returns to the configured default rate without manual intervention.

### UI improvements

- **Customize, save and share table views.** Show or hide columns in object lists, relationship tabs, and IPAM address and prefix lists from the **Columns** menu in the toolbar. Bookmark your customized view for later use or share it with other users via the page URL.
- **Read labels and follow connections in SVG diagrams.** Zoom into large diagrams and pan across them in the artifact and file object viewers.
- **Run a Generator from an object's detail page.** You can now [start a Generator](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/generators/overview.mdx) for the service or device you're viewing from its **Actions** menu. The run processes that object only, rather than every member of the Generator's target group.
- **Choose the kind of IP address or prefix to allocate from a pool.** When a relationship accepts several IP address or prefix kinds, the **Type to allocate** field on the **From pool** tab lets you choose which kind to create, instead of always using the pool's default kind. See allocating [addresses](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/allocate-ip-address.mdx) and [prefixes](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/allocate-ip-prefix.mdx) from a pool.

### Identify objects from webhook payloads without additional API queries

[Webhook payloads](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/webhooks/overview.mdx#identifying-objects-in-node-events) now include:

- The human-friendly ID of the object that changed.
- Display labels and human-friendly IDs for related objects.

Webhooks with **Branch scope** set to **Default Branch** now also trigger correctly for branch merges and Proposed Change reviews.

### Python SDK

#### Query selected data directly with the Python SDK

You can now use `only` to [retrieve a specific set of attributes and relationships](https://github.com/opsmill/infrahub-sdk-python/blob/a3c30b0ff52eb2f720d703f5bf4a13d263bd629b/docs/docs/python-sdk/guides/query_data.mdx#fetching-only-the-named-attributes-and-relationships), along with required object identifiers. This lets you limit the data your script retrieves without writing a custom GraphQL query.

#### Respond to specific API errors

You can now define how your automation responds when a required attribute is missing, a uniqueness constraint is violated, or a branch needs rebasing. In your Python code, use a `try`/`except` block to [identify the specific SDK exception and read its error details](https://github.com/opsmill/infrahub-sdk-python/blob/a3c30b0ff52eb2f720d703f5bf4a13d263bd629b/docs/docs/python-sdk/topics/error_handling.mdx), such as the fields involved in a uniqueness violation, without parsing error-message text.

- **Set connection timeouts separately from API response timeouts.** You can now configure your Python automation to stop a connection attempt after, for example, 5 seconds while allowing up to 60 seconds to receive an API response once connected. The new [connection timeout](https://github.com/opsmill/infrahub-sdk-python/blob/a3c30b0ff52eb2f720d703f5bf4a13d263bd629b/docs/docs/python-sdk/reference/config.mdx#connect_timeout) defaults to 10 seconds.

### Security fixes

- **Prevent unauthorized API token deletion.** Fixed an authorization flaw that allowed a signed-in user who knew another account’s API token ID to delete that token, potentially interrupting automation that used it.
- **Apply global permission changes only after merging.** Fixed an issue where changes to account group membership, roles, or [global permissions](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/user-management/permissions-roles/overview.mdx#global-permissions) on an Infrahub branch could alter users’ access before the branch was merged into the default branch.
- **Exclude sensitive information from traces.** Removed SSO credentials and identity-provider user details from OpenTelemetry traces. Infrahub also [masks sensitive trace attributes](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/install-configure/install/observability-stack.mdx#values-that-spans-never-contain), including client IP addresses, URL query strings, and account names, before export. Previously stored traces remain unchanged; this masking does not apply to log entries.
- **Fix GraphQL denial-of-service vulnerabilities.** Updated `graphql-core` to address vulnerabilities that could cause excessive CPU or memory consumption when processing queries: [CVE-2026-75507](https://github.com/graphql-python/graphql-core/security/advisories/GHSA-vj8h-fx38-h3vc) and [CVE-2026-75508](https://github.com/graphql-python/graphql-core/security/advisories/GHSA-r77w-qph3-7vf8).

### Breaking changes and required actions

#### Git repositories

**Errors in files referenced by `.infrahub.yml` now stop the Git import.** The following problems previously allowed the import to continue or caused a failure later, when generating an artifact:

- A schema file or directory does not exist, or a schema directory contains no `.yml`, `.yaml`, or `.json` files.
- A Jinja2 template file is missing, empty, outside the repository, not UTF-8 encoded, or has invalid syntax.
- A Python Transformation or check names a class that is not defined in the specified Python file.

Before the next import after upgrading, correct these references or files, or remove definitions that are no longer needed. The [repository import documentation](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/git-integration/overview.mdx#entries-in-infrahubyml-that-fail-the-import) explains how to identify and resolve the errors.

**Merging an Infrahub branch now fails if a required Git repository import failed or has not completed.** The branch and its Proposed Change stay open, and the error identifies the repository. For branches synchronized with Git, the merge also fails if Infrahub has not recorded the latest Git commits. These [checks apply to both Proposed Changes and direct branch merges](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/branches/merge.mdx#before-the-merge-starts-repository-imports).

**Read-write Git repositories require credentials with write access.** When adding a repository to Infrahub, use a Git account or access token that can write to that repository. No action is required for existing repositories before upgrading; credentials are checked when you add a repository or run **Check connectivity**.

**Check connectivity** does not test branch protections or push rules. A successful check does not guarantee that the Git server will accept a later push.

**Adding a read-write Git repository now fails if its configured `default_branch` does not exist in Git.** This setting identifies the Git branch imported into Infrahub’s default branch and defaults to `main`. When adding a repository, set it to the existing Git branch you intend to use. Infrahub does not automatically select the Git server’s default branch. Read-only repositories are unaffected. See [connecting a repository](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/git-integration/connect-repository.mdx).

**Branches with Sync with Git disabled no longer import changes from Git.** **Before upgrading**, check whether your workflow relies on pushing changes to a Git branch and importing them into an Infrahub branch created with this setting disabled. To continue importing those changes, use a branch created with **Sync with Git** enabled. Infrahub’s default branch is unaffected.

**Removing the last object file from a Git repository now deletes the objects it defined.** Infrahub tracks the objects that each repository's object files define and, on every import, deletes the tracked objects that the files no longer define. This already happened when you removed one object file among several. It now also happens when you remove the last object file or clear the `objects:` list in `.infrahub.yml`, which previously left those objects in Infrahub.

If you made either change before upgrading, those objects are deleted during the first import after upgrading. **To keep them, restore the object files and their `objects:` entries before upgrading.**

If another object still refers to one of these objects through a mandatory relationship, the import reports a warning instead of deleting it, and the next import tries the deletion again.

#### Generators

**Objects tracked by a Generator are now deleted if no `save()` calls are made when you run it.** For example, if your Generator code calls `save()` only when values change, the existing objects can be deleted when all values are unchanged.

**Before upgrading**, update your Generator code to call `save()` for every object in the Generator group that you want to retain, including unchanged objects.

**Running the Generator on a separate branch does not protect branch-agnostic objects from deletion.** These objects are shared across branches. If deleted during the Generator run, they are removed from the default branch immediately, without a merge.

If you use a Generator to update existing objects that should remain independently of the Generator—for example, adding a checksum to a device—use `save(update_group_context=False)`.

**Before running the updated Generator**, remove those objects from its Generator group if they are already members. Changing the `save()` call alone does not remove their membership, and they can still be deleted.

#### Number pools and IP pools

**Before allocating numbers after upgrading**, [attach manually assigned values within the pool’s ranges to that pool](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/track-existing-numbers.mdx). The existing values remain unchanged and are excluded from subsequent allocations.

**Number pools for the same unique attribute can no longer have overlapping ranges.** If existing pools overlap, [attach the numbers assigned within the overlapping range to one pool](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/track-existing-numbers.mdx), then change the other pool’s ranges to remove the overlap.

**When you attach a number pool to an attribute that already holds a non-default number, specifying `from_pool` alone now returns an error.** Send the existing `value` with `from_pool` to retain the number, or `value: null` with `from_pool` to request a replacement. Naming the pool that already tracks the attribute leaves its number unchanged. If the attribute is empty or still holds its schema default, `from_pool` alone allocates a number. The [number-pool documentation includes examples of both options](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/track-existing-numbers.mdx#send-the-number-with-the-pool-not-the-pool-alone).

**Renaming a kind or attribute used by a number pool now fails schema validation.** While the pool exists, changing the kind’s namespace or making it inherit from another generic is also restricted. Before loading schema changes, check whether they affect [kinds or attributes used by number pools](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/schema/migration.mdx#number-pool).

**Allocating an IP prefix through the API now fails if `prefix_type` specifies a kind that the relationship does not accept.** If your scripts specify `prefix_type`, update them to use a kind accepted by the relationship receiving the allocated prefix.

**Setting a number attribute to `null` through the API now requires detaching its assigned number from the pool.** This also applies when resetting the attribute to its default or assigning a number outside the pool’s ranges. Include `from_pool: null` in the same API update as the value change. The [documentation includes examples of detaching a number](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/resource-manager/track-existing-numbers.mdx#detach-a-number-from-its-pool).

**Creating, updating, or deleting number-pool ranges now requires permissions on `CoreNumberPoolRange`.** Before users or service accounts perform these operations, grant the corresponding create, update, or delete permission in addition to their pool permissions. This includes [creating a pool with ranges](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/release-notes/deprecation-guides/number-pool-ranges.mdx#create-a-pool).

**Scripts that read whole-pool usage from `InfrahubResourcePoolUtilization.edges` must now use the top-level fields instead.** After upgrading, entries in `edges` contain usage for individual ranges. Update those scripts to read `utilization`, `utilization_default_branch`, and `utilization_branches` directly from the query result.

#### Authentication

**Check SSO account links.** `INFRAHUB_SECURITY_SSO_ACCOUNT_NAME_FALLBACK` now defaults to `false`. If an existing account is not linked to its SSO identity, its first SSO login creates a separate account or fails instead of linking by display name. Linked accounts are unaffected. Complete linking before upgrading, or plan a controlled migration using the [SSO migration guide](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/release-notes/deprecation-guides/sso-account-name-fallback.mdx). Temporarily enabling the fallback retains its account takeover exposure when users can change display names; disable it after linking. Removal is scheduled for 1.13.

#### Deployment and monitoring

**Deployments using NATS must switch to RabbitMQ and Redis before upgrading.** The experimental NATS drivers have been removed. If `INFRAHUB_BROKER_DRIVER` is set to `nats`, configure RabbitMQ as the message broker. If `INFRAHUB_CACHE_DRIVER` is set to `nats`, configure Redis as the cache. Infrahub 1.12 cannot start with either driver set to `nats`.

**API server logs now use a different trace ID format.** The `trace_id` field now contains exactly 32 lowercase hexadecimal characters, including leading zeros, without the previous `0x` prefix. Update log queries, parsers, and alert rules that depend on the previous format. See [correlating logs and traces](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/run-observe/own-monitoring.mdx).

**When tracing is enabled, Infrahub now records 10% of new traces by default instead of every trace.** To continue recording every new trace, set `INFRAHUB_TRACE_SAMPLE_RATIO=1` on the API server and every task worker before starting the upgraded services. Requests that arrive with an existing trace context retain the caller’s sampling decision. See [trace sampling](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/install-configure/install/observability-stack.mdx#trace-sampling).

**The standalone Docker Compose observability stack now enables tracing by default.** Set `INFRAHUB_TRACE_ENABLE=false` if you do not want it enabled.

**Custom Gunicorn startup commands must now load Infrahub’s metrics configuration.** Add `--config backend/infrahub/serve/gunicorn_config.py` to the command before starting 1.12. Without it, `/metrics` continues reporting gauge values from stopped workers. The supplied Docker Compose files and Helm charts already load this configuration. See [API server metrics](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/run-observe/metrics.mdx#where-metrics-are-exposed).

#### API clients and local commands

**Local `infrahubctl` commands now use the configured default Infrahub branch instead of the current Git branch.** This affects Generators, Transformations, and checks run without an explicit branch selection. The configured default is `INFRAHUB_DEFAULT_BRANCH`, which defaults to `main`. If you previously relied on your Git checkout to select a test branch, you could now read or change data on `main` instead.

Before running these commands after upgrading, pass `--branch` to select the intended Infrahub branch. To retain the previous behavior, set `INFRAHUB_DEFAULT_BRANCH_FROM_GIT=true`. See [branch configuration](https://github.com/opsmill/infrahub-sdk-python/blob/a3c30b0ff52eb2f720d703f5bf4a13d263bd629b/docs/docs/python-sdk/reference/config.mdx#default_branch_from_git).

**The wording of some SDK API error messages has changed.** If your Python code compares error-message text to decide what to do after a failure, those comparisons may no longer match after upgrading the SDK. For example, code intended to continue after a duplicate-value error could stop instead.

Before upgrading the SDK, replace these text comparisons with checks on `exc.code`, such as `exc.code == "UNIQUENESS_VIOLATION"`, or catch the corresponding exception class. See [SDK error handling](https://github.com/opsmill/infrahub-sdk-python/blob/a3c30b0ff52eb2f720d703f5bf4a13d263bd629b/docs/docs/python-sdk/topics/error_handling.mdx).

**SDK tracking-group cleanup failures now raise `TrackingGroupCleanupError` instead of `GraphQLError`.** If your code catches `GraphQLError` around Generator or tracking-group cleanup, also catch `TrackingGroupCleanupError`. Failures such as a lost connection still raise their original exception.

**SDK protocols now define related object types more precisely and correct the base classes used by generated synchronous classes.** If you use these definitions to type-check your Python automation, your type checker may report new errors after updating. Protocols describe the attributes, relationships, and methods available on Infrahub objects.

If you maintain generated protocols for your schema, regenerate them with `infrahubctl protocols` to use the corrected definitions. Run your type checker after updating and review any new errors. See [updating generated protocols](https://github.com/opsmill/infrahub-sdk-python/blob/a3c30b0ff52eb2f720d703f5bf4a13d263bd629b/docs/docs/python-sdk/guides/python-typing.mdx#keep-protocols-in-sync-with-your-schema).

**The SDK’s `CoreGenericAccount` protocol no longer includes `tokens` or `external_identities`.** These relationships were present in the Python definition but were not available through the API. If your code references either relationship on `CoreGenericAccount`, review how that code retrieves account tokens or external identities before updating the SDK.

**API operations now return HTTP 503 instead of 500 if Infrahub cannot start a background task or monitor it through completion.** This affects operations where the API waits for the task’s result. If your integration handles this condition by checking for HTTP 500, extend that handling to include HTTP 503 before upgrading Infrahub.

**A GraphQL query now fails before execution if validating it requires more than 250,000 field comparisons.** The API returns `Query is too complex to validate`. This limit applies to comparisons between field selections while checking the query, not to the number of objects returned.

If you encounter this error after upgrading, simplify repeated field selections or divide the query into smaller requests, then test again.

### Deprecations

**`start_range` and `end_range`, which define the lower and upper limits of a number pool, are deprecated in favor of `ranges`.** These fields remain supported in 1.12 for pools with a single range. If you add multiple ranges to a pool, reading the old fields returns `null`, and attempts to change them fail.

Replace the old fields with `ranges` in schema definitions and in code that creates pools or reads or changes their ranges. Make these code changes before adding multiple ranges to a pool. If you use the Python SDK or `infrahubctl`, first upgrade to `infrahub-sdk` 1.24.0 or later; earlier versions do not support `ranges`.

Follow the [number-pool migration guide](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/release-notes/deprecation-guides/number-pool-ranges.mdx) for schema, GraphQL, and Python SDK examples. The guide does not specify when the old fields will be removed.

**From 1.13, a first SSO login will no longer give access to an existing Infrahub account just because the names match.** If you are moving users from local passwords to SSO, complete the [account migration procedure](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/release-notes/deprecation-guides/sso-account-name-fallback.mdx) before upgrading to 1.13 so they can keep their existing accounts and permissions.

The name-matching option, `security.sso_account_name_fallback`, is already disabled by default in 1.12. The guide explains how to use it temporarily for migration and disable it afterward. Users whose SSO login is already connected to their Infrahub account are unaffected.

**`infrahub-sdk` 1.24.0 is the last SDK release that supports Python 3.10.** If your automation uses Python 3.10, upgrade its Python environment before installing the next SDK release.

**`infrahub-testcontainers` 1.12.0 is the last version that supports Python 3.10.** This package starts Infrahub instances in Docker for integration tests. If you run those tests with Python 3.10, update the Python environment that runs them—including any CI jobs—before installing the next package release. Python 3.10 remains supported with version 1.12.0.

### Upgrade an existing instance

**To upgrade to Infrahub 1.12, your instance must first be on 1.11.** If you are on 1.10 or older, upgrade through each intervening minor version—for example, 1.9 → 1.10 → 1.11 → 1.12.

Complete applicable [upgrade preparation](#before-you-upgrade), back up the database, and test restoration. Remove branches you no longer need to reduce migration processing. See [backup and restore](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/maintain-upgrade/database-backup/overview.mdx).

Follow the instructions for [Community](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/maintain-upgrade/upgrade/community.mdx) or [Enterprise](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/maintain-upgrade/upgrade/enterprise.mdx). Use the 1.12.0 images and run `infrahub upgrade` in the upgraded environment.

After the command reports `Upgrade complete SUCCESS`, run `infrahub db showmigrations` against the same database. Confirm that every migration is marked `[X]` and that the database version matches the target version.

Restart the services specified in your deployment guide, including the API server and task workers. Workers that remain running from before the migration can continue using the old schema.

If the upgrade reports branches that need rebasing, rebase them before merging. You can rebase them individually afterward or include `--rebase-branches` when running `infrahub upgrade`.

If you use the observability stack, follow its [upgrade instructions](https://github.com/opsmill/infrahub/blob/99b0f19f17b674642d757506a9438bb4c3db4032/docs/docs/deploy-manage/maintain-upgrade/upgrade/observability-stack.mdx). Docker Compose deployments may require services to be recreated to load updated monitoring configuration.

Existing number pools keep their allocated numbers. Each pool initially contains one range with its previous lower and upper limits.

The first Git repository import after upgrading reruns Generators, regenerates artifacts produced by Python Transformations, and recalculates Python computed attributes. Complete the Generator preparation described in the breaking changes before this import.

That import also deletes repository-managed objects whose defining files were removed. Restore the files and their `objects:` entries before upgrading if those objects must remain.

If you revert to an earlier version while pushes to remote Git repositories are pending, they do not resume automatically. Push the changes manually or merge again, then run a full regeneration of the default branch to replace the regeneration that was waiting for the pending pushes.

### Full changelog

**Security**

- Fixed an issue where an account signed in with a JWT token could delete an API token that belongs to another account, including an administrator account, if it knew the ID of that token.
- Fixed security vulnerabilities in frontend rendering, tracing, documentation, and development dependencies.
- Upgraded `graphql-core` from 3.2.8 to 3.2.13, which fixes two denial-of-service vulnerabilities in the library, CVE-2026-75507 and CVE-2026-75508. The GraphQL API now rejects a query whose validation needs more than 250,000 field comparisons with a "Query is too complex to validate" error.

**Removed**

- Removed the skip of numbers already set on a unique attribute when a number pool allocates, added in 1.10.8 and 1.11.0: a pool now offers only numbers its own records leave free, so before allocating from a pool whose range holds numbers set by hand, attach each of those numbers to the pool by saving its object with the number as `value` and the pool as `from_pool`.
- Removed the experimental NATS JetStream driver for the message bus and the cache, so a deployment that sets `INFRAHUB_BROKER_DRIVER` or `INFRAHUB_CACHE_DRIVER` to `nats` now fails to load its configuration and must use RabbitMQ and Redis.

**Deprecated**

- Deprecated `start_range` and `end_range` on `NumberPool` attributes and on `CoreNumberPool` in favor of `ranges`; see [How to migrate number pools to `ranges`](https://docs.infrahub.app/release-notes/deprecation-guides/number-pool-ranges).
- The deprecated `INFRAHUB_SECURITY_SSO_ACCOUNT_NAME_FALLBACK` (`security.sso_account_name_fallback`) setting and the account-name fallback it controls will be removed in Infrahub 1.13, after which a first SSO login never claims an existing account. See [How to migrate off the SSO account-name fallback](https://docs.infrahub.app/release-notes/deprecation-guides/sso-account-name-fallback).
- Deprecated support for Python 3.10 in the `infrahub-testcontainers` package. Infrahub 1.12.0 is the last release of `infrahub-testcontainers` that supports Python 3.10, and the next release removes that support.

**Added**

- Added Repositories and Git state columns to the branches list, showing each branch's Git repositories with the worst Git state first and a link to the branch for the full list.
- Added an alpha dark theme that follows the operating system's appearance by default, with System, Light, and Dark available from the Theme option in the account menu.
- `CoreGenericRepository` now defines a `commit` attribute, so the current commit of any repository can be read without knowing whether it is a managed or a read-only repository. Both concrete kinds continue to override the attribute with their own branch scope, so their behaviour is unchanged.
- Added the handling of a failed push to the Git remote after a branch merge. When Infrahub cannot push the merge of a branch to the remote of a read-write repository, the merge stays complete in Infrahub and waits in the push queue of the repository until the push succeeds or a user abandons it. Infrahub retries the push automatically when the cause can clear by itself, for example an unreachable remote, and records the cause and the message of the remote on the repository. Nine new read-only attributes of the repository, such as `delivery_status`, `delivery_failure_cause` and `delivery_queue`, show the push state through GraphQL. The new `InfrahubRepositoryDeliveryRetry` mutation pushes the pending merges again, and the new `InfrahubRepositoryDeliveryAbandon` mutation drops them.

  The details page of a read-write repository shows the push state in a **Push to remote** card: the status, the cause and the required action of a failed push, the message of the remote, the pending merges, and the last abandoned push. The **Retry push** and **Abandon pending push** actions of the repository menu push the pending merges again or drop them, and a disabled action shows why it is unavailable.

  While pushes are pending, Infrahub does not import the remote default branch of the repository, refuses **Reimport current commit** and the conversion to a read-only repository, keeps the remote source branch of a pending merge, and holds the artifacts, Generators and Python computed attributes that the repository defines until the push succeeds or the queue is abandoned. If someone pushes to the remote default branch while pushes are pending, Infrahub refuses to merge another branch that changes the files of the repository until the pending pushes reach the remote or are abandoned. Infrahub also records a pushed commit that a later rewrite of the remote default branch removed, and stops the fetch and the push of the pending merges when an HTTP or HTTPS remote stalls.

  When Infrahub cannot start a background task in the task manager, or cannot follow the task until it ends, an API request that waits for the result of that task now fails with the HTTP status 503 (service unavailable) instead of 500.

  A revert to an earlier version keeps the data valid, because the earlier version ignores the nine new `delivery_*` attributes of the repository. Two effects remain after a revert. Merges still in a push queue are never pushed: push them by hand, or merge again. Held regeneration is never released: run a full regeneration of the default branch.
- When allocating a resource from an IP pool through a relationship that points at the generic `BuiltinIPAddress` or `BuiltinIPPrefix`, the target object kind can now be chosen instead of always using the pool's `default_address_type` / `default_prefix_type`. In the UI, the "Type to allocate" field of the "From pool" tab selects which concrete kind is allocated; over GraphQL, pass `address_type` (new on `IPAddressPoolInput`) or `prefix_type` inside `from_pool`.

  The requested kind is validated server-side: it must be one of the kinds implementing the relationship's peer generic, and it cannot be changed on an identifier that already holds a reservation. Note that `prefix_type` was previously accepted on `IPPrefixPoolInput` without any validation, so a client sending a kind unrelated to the relationship's peer now receives an error instead of an unexpectedly-typed node.

  Object templates are not covered: a template's `<relationship>_from_resource_pool` link stores only the pool, so an object created from a template still allocates the pool's default kind. Sending a target kind or a prefix length on that link previously made the mutation fail, and is now correctly omitted.
- Choose which columns a list view shows. Every schema-driven table — the object list, relationship tabs, and the IPAM address and prefix lists — now has a **Columns** control. Wherever column headers offer a menu, that menu also carries a **Hide column** shortcut; relationship tabs have read-only headers, so there the Columns control is the way. The control stays open as you tick columns on and off, so setting up the view you want is a single visit.

  Your choice lives in the URL, so a reload keeps it and the link can be shared with a colleague who will see the same view. On the object list you can also reveal attributes the schema marks as secondary (`display: "extra"`), which previously had no way to appear in a list at all. Only the columns you change are recorded, so a schema that later gains a column shows it on an existing link. Reset restores the schema's own layout.
- Read-only repositories are now checked for upstream movement of the refs they track, so a branch or tag that advances on the remote is noticed without waiting for someone to trigger an import. The check runs on a schedule. A user with permission to update the repository can also start it from the "Check remote now" button on the repository's Commits tab, or through the `InfrahubReadOnlyRepositoryCheckRefs` mutation, which previously accepted a request and did nothing. Every check that reaches the remote records a check time, which the Commits tab shows even if the remote has not moved. A repository whose tracked ref has moved has the new objects brought into every worker's copy, while the commit Infrahub has imported stays exactly where it was: nothing here writes the tracked commit, triggers an import, or changes which commit a worker has checked out.

  `INFRAHUB_GIT_READ_ONLY_REFS_CHECK_INTERVAL_MINS` sets how long the system waits before checking one repository again, defaulting to 15 minutes. Lengthening it is the way to make the check less frequent; an idle repository costs one refs listing per interval and transfers nothing. A repository whose remote cannot be reached is recorded with the reason and retried sooner than a full interval, without holding up the others.

  When the check finds that a tracked branch or tag has been deleted from the remote, the repository's sync status shows "Tracked Ref Missing" on the default branch, if it tracks that ref, and on every branch that set its own ref to it. Those other branches fail their proposed-change check and cannot be merged. A branch that only inherits the default branch's ref is not affected. To recover, restore the ref on the remote or change the repository's ref, then run "Reimport current commit". A reimport run while the ref is still missing keeps the status.
- Added the GraphQL API for repository git visibility. `InfrahubRepositoryCommits` answers for the branch you are viewing with the remote branch or tracked ref it follows, the commit Infrahub has imported, and a paged commit log read live from a worker's local copy, each commit labelled as imported, pending, history, unrelated or at the remote head. On a branch that does not sync with Git, it lists the repository's own default branch and labels the commits the branch does not run yet as not on this branch, since only a rebase brings them to the branch, except the newest, which stays the remote head; on the branch a repository was added on, those commits stay pending import until the branch is merged. It reports when the remote history was rewritten, when the imported commit no longer exists in the local copy, and when a read-only repository's tracked branch or tag has been deleted upstream as of the worker's last fetch, in which case it still lists the history Infrahub is running. A worker that has no local copy yet answers that the log is not available and starts a single background clone that reaches every worker; a read-write repository that has imported nothing yet is instead left to its next sync, which creates the copy along with the first import. `InfrahubReadOnlyRepositoryCheckRefs` is published alongside it so consumers can build against the full surface.
- The repository page has a new Commits tab. Once Infrahub can read a repository's commit history, the tab lists the commits of the branch you are viewing, newest first, with the short hash, summary, author and date of each one. It marks the commit Infrahub has imported and the current head of the remote, shows how many commits are pending import, and says when the tracked ref was rewritten so the imported commit is no longer part of its history. On a branch that does not sync with Git, for a read-write repository that was not added on that branch, the tab lists the history of the repository's default branch, says how many commits the branch is behind it or that it is up to date, and marks those commits as behind. When the branch is behind, has diverged from the default branch, for example after a force push, or uses a commit that is missing from the remote, it asks for a rebase, which moves the branch to the commit Infrahub's default branch uses. For a read-write repository added on that branch, the tab says the next sync imports its pending commits. The tab title shows how many commits are waiting and whether an import or a rebase is needed, and a warning when the history was rewritten, the imported commit is missing from the remote or the tracked ref was deleted. The top of the tab states whether the branch is up to date, behind, diverged or waiting for an import, says what brings the missing commits, and shows the tracked ref and when the remote was last checked. It offers Import latest commit and Check remote now on a read-only repository, and Rebase branch on a branch that does not sync with Git, after a confirmation that the whole branch is rebased onto the default branch. It also offers Check remote now when the commit log of a read-only repository is not available, and says when a read-only repository has imported no commit yet and offers Import latest commit. Check remote now is offered only for a read-only repository that is active on the branch you are viewing, so not for one added on that branch. When the tracked ref of a read-only repository no longer exists on the remote, it says to change the tracked ref in the repository's Edit form or restore it in Git. While an import, a rebase or a check runs, the tab says so. A disabled action says why it is disabled: you are not signed in, the branch needs a rebase, is being merged, is merged or its merge failed, you lack the permission, or the branch is the default branch. Each commit has a menu to copy its full hash or, for repositories hosted on GitHub, view the commit on GitHub.

  Until Infrahub can read a repository's commit history, the tab says the commit log is not available.
- Connecting a repository now checks that its configured default branch exists on the remote, as part of the connectivity check that already runs. When the branch is absent, the request is rejected with an error naming the branch Infrahub looked for and, where the remote has one, the branch it uses as its own default. No repository is left behind - previously the repository was created and only failed later, during its first synchronization. A default branch that exists but differs from the remote's own default is a supported configuration and is accepted. Read-only repositories are unaffected: their `ref` may be a tag or a commit hash, which a branch listing cannot confirm.
- When a read-write repository's `default_branch` differs from Infrahub's default branch, Infrahub cannot import a remote branch with the same name as Infrahub's default branch. Infrahub now records that skipped branch as a warning in the repository's Tasks tab, not only in the worker's process log. The warning appears when you add the repository on Infrahub's default branch, and again on any synchronization that imports a branch or detects a new commit on the skipped branch. Successful synchronizations where nothing changed on the remote add no task. With more than one task worker, a push to the skipped branch is not always reported, and the same push can be reported more than once.
- See at a glance how a repository stands on every branch. A repository's detail page now carries a **Branches** card listing one row per branch — the branch name, the branch status, its sync status, the commit shown for that branch, and, for a read-only repository, the ref it tracks — with the default branch marked and the total shown beside the title.

  The card is paginated, and searching or filtering narrows the set on the server rather than in the browser, so the count and the pages always describe the same set. Filter by branch name, branch status or sync status, for example to list only the branches whose import failed, and sort by when a branch was created or last updated. The page, the filters and the sort all live in the URL, so a reload keeps the view and the link can be shared with a colleague.

  A repository's details are also split in two, so it is clear which values describe the whole repository and which describe only the branch you are on: a repository-wide card, then an **On this branch** card captioned with the branch name, then the branches card. Switching branch changes the second card alone. Every other kind of object keeps its single details card.
- Added the allocation scopes of a number pool to its details page. The page lists the pool's allocation scopes, sorted by usage and searchable, and opens the ranges and allocated numbers of one scope on the same page, kept in the address so it can be shared. A pool with an allocation scope no longer shows ranges and numbers for the whole pool, and the header names the fields the pool is scoped by.
- Added a Repository activity card to the repository page, which shows the run working on the repository now with its step, branch and running time, who holds the repository lock, and what the last run of each operation changed or failed on.
- When the import of a Git repository branch fails, the task log now names the import step that was running when the import stopped, the steps that ran before it and the steps that did not run, or states that nothing was imported when the failure happened while the repository was read. A step with nothing to import is listed among the steps that ran. A failure caused by a connection or credential error is not followed by this summary.
- Added the branch's Git repositories and tasks to the branch details page, on branches other than the default branch. The repositories table shows each repository's Git state and commit. When an import fails, the page shows the last error line of the failed import when it can find it, and when a repository's remote can't be reached, it shows a warning that the commit shown may be out of date. The tasks table lists the tasks that ran on the branch.
- Added a "Number" input to the "From pool" tab of a number attribute in object forms, so you can type a number and record it in the selected number pool; when editing, typing a number in the "Value" tab removes the number from its pool.
- Added the `InfrahubRepositoryActivity` GraphQL query, which shows the runs working on a repository now, the last run of each operation and which worker holds the repository lock, with the same answer on every branch.
- Added the `InfrahubRepositoryBranchStatus` GraphQL query, returning one row per branch with the repository's `commit`, `sync_status` and `internal_status` as that branch resolves them, plus `ref` for a read-only repository, filterable with `name__value`, `partial_match`, `status__value`, `sync_status__value`, `internal_status__value`, and `own_values_only`.
- Added a proposed change check that fails when the last object import of a repository on the source branch failed or has not completed, blocking the merge until the import succeeds.
- Added the `last_rewrite_previous_commit`, `last_rewrite_commit`, `last_rewrite_at` and `rewrite_count` attributes to Git repositories, which record per branch the commit Infrahub had imported before the remote history was rewritten, the commit it moved to, when that happened and how many rewrites the branch has seen, including those on the default branch before the branch was created, and which do not count a change of the repository's default branch as a rewrite; on a read-only repository, "Import latest commit" updates them when the tracked branch was force-pushed, and does not count a change of `ref` or `commit` as a rewrite unless it runs while that change is still being applied.
- Added a repository sync status indicator to the application header. It turns red with a pulsing dot when any Git repository on the branch you are viewing has failed to import, on every page, and links straight to the repository list filtered to those failures.

  It reads repository sync status rather than task state, so an import that left the branch broken is reported even when the task that ran it finished successfully. When nothing is failing it links to the full repository list, and it always reports current status regardless of the time-frame selector.
- The daily anonymous telemetry report now includes the CPU and memory available to the API server and the task workers, and the CPU count and memory set for the database. Two new blocks, `server` and `task_workers`, count the processes of each component the same way `workers` does. Each also reports `processes_per_container`, the number of processes that share one container, and a `per_container` object with the CPU count a process in that container can use (`processor_available`), the CPU limit set on the container (`processor_assigned`), and the memory and free memory of the container (`memory_total`, `memory_available`). Multiplying `per_container` by `active` and dividing by `processes_per_container` gives the total for the component. The database block gains `processor_assigned`, the CPU count set for the Neo4j parallel query engine, and `memory_heap_max_size` and `memory_pagecache_size`, the Neo4j heap and page cache sizes as Neo4j reports them, such as `1.00GiB`, or `null` when not set. The `workers` block and every other existing field are unchanged, and a new figure that cannot be read is reported as `null` without affecting the rest of the report.
- Added the type and version of the task manager database, such as PostgreSQL 16.4, to the anonymous usage telemetry.
- Added a Generators section to an object's Actions menu that runs a Generator for that object only, listing the Generators whose target group contains objects of the same kind.
- Added telemetry to find which component makes an instance slow. When the Python SDK sends the trace context, a background task shares one trace with the API calls and database queries it sends. `INFRAHUB_TRACE_SAMPLE_RATIO` sets the share of recorded traces (default 0.1), and an administrator can raise it for up to 24 hours without a restart through `/api/troubleshooting/trace-sample-ratio` or `infrahubctl troubleshooting trace-sample-ratio`. New metrics show long query and request durations, connection pool usage and task worker queue delays. Traces no longer contain single sign-on secrets and mask personal data, the bundled Grafana dashboards work in any Grafana, and the Compose observability stack turns tracing on. `gunicorn` must start with `--config backend/infrahub/serve/gunicorn_config.py`, as the Compose files and Helm charts do.
- Added pan and zoom to SVG files in the artifact and file viewers: drag to pan, and zoom with the mouse wheel or the zoom in, zoom out, and reset buttons.
- Added the `--performance-result-compress`, `--performance-result-required` and `--performance-result-file` options to the `infrahub-testcontainers` pytest plugin, which send the performance results gzip-compressed, fail a passing session when the results cannot be stored, and also write them to a file.
- Uniqueness constraint violations on GraphQL mutations now return the catalogued `UNIQUENESS_VIOLATION` code instead of falling back to `UNDEFINED_ERROR`. The `extensions.data` payload carries `node_kind` and `fields`, so consumers can identify the colliding constraint members (which may be relationships as well as attributes) without parsing the error message. HFID collisions resolve to the same code.
- Connecting a read-write `Repository` now verifies that Infrahub can push to the remote, not only read from it. A credential that can read but not push is caught when the repository is connected, and the connection is rejected with a credential error naming the cause, rather than the problem surfacing later at the first branch creation or merge. Read-only repositories are unaffected. A push that fails at the transport level (for example an expired token or a refused connection) is now classified and recorded on the repository's operational status the same way a fetch failure already was.

  The write check is effective on Git servers that enforce write authorization when advertising the receive-pack service (such as GitHub and GitLab). It confirms repository-level write access and does not evaluate branch protection, push rules, or pre-receive hooks. ([#10637](https://github.com/opsmill/infrahub/issues/10637))
- Node events delivered to webhooks now identify the objects they mention: the changelog carries the node's human-friendly ID (`hfid`), and each relationship peer carries its display label (`peer_display_label`) and human-friendly ID (`peer_hfid`). This applies to node mutations and to the node events a branch merge or rebase emits, so a receiver no longer has to query Infrahub to resolve the IDs. ([#9671](https://github.com/opsmill/infrahub/issues/9671))

**Changed**

- When a change to a related object alters a display label or human-friendly ID, only the artifacts and Generator instances of the targets that show that label or ID are now regenerated after a merge or in a Proposed Change, instead of every target of the definition.
- Post-merge regeneration now narrows to the affected members when the changed data is read through a relationship, such as an interface field used in a device's configuration, instead of regenerating every member of the definition. Changes that cannot be attributed to specific members still regenerate the whole group.
- Mermaid diagrams in Markdown now use Pele, with an updated style that follows the Infrahub theme.
- Reduced the load that the artifact checks of a proposed change put on the API server, which grew with the square of the number of artifacts to check.
- Deprecated attributes and relationships of the nodes that Infrahub provides no longer produce a warning in the server logs each time the schema is processed, including at startup. Deprecated attributes and relationships of your own schema nodes still produce this warning.
- Shortened the validation of a proposed change with many checks and reduced the requests it sends to the task manager: Infrahub now reads the state of all the runs a validation waits on together, once a second, instead of reading each run separately.
- Generators now try to delete every node from an earlier run that the current run does not save again, including when a run saves no nodes at all. Previously, a run that saved nothing deleted nothing, and the cleanup stopped at the first node it could not delete, so nodes the Generator no longer produced could stay in place. Now a node the server refuses to delete stays in the Generator's group, the cleanup continues with the other nodes, and the Generator run reports an error. Any other failure, such as a lost connection or an expired token, stops the cleanup, and the nodes it has not reached stay in the group. On a branch, the cleanup deletes on that branch, and deleting a node of a branch-agnostic kind removes it from every branch, including the default branch.

  Before upgrading, check Generators that skip saving nodes when their inputs have not changed: those nodes are now deleted on the next run. A Generator must save every node it wants to keep on every run. Nodes that a Generator updates but does not own, such as a node it only adds a checksum to, should be saved with update_group_context=False so they are not added to the Generator's group. A node that an earlier run already added to the group is still deleted on the first run that saves it with update_group_context=False, so remove it from the Generator's group before that run.
- A merge or a rebase no longer starts one recompute task per changed node for Python transform computed attributes. It now derives the affected attributes from the whole change set and submits one recompute per affected attribute per batch of changed nodes, as it already did for Jinja2 computed attributes, display labels and human-friendly ids. The stored values are the same.

  An attribute whose transform query is not pinned to a single object recomputes its whole kind instead. Pin the query to get the narrowed recompute. See [Single-target queries](https://docs.infrahub.app/development-resources/graphql/single-target-queries).
- A live change to a node that feeds a Python transform computed attribute no longer starts duplicated recompute tasks. A change to a node the transform query reads now recomputes only the attributes that query feeds, on the nodes that read the changed node through it, instead of every Python computed attribute of every kind subscribed to any query group that holds the changed node. The stored values are the same.

  The automations that carry this are rebuilt on the next reconcile, which `infrahub upgrade` performs, so the previous behavior continues until then.
- Limited how long Infrahub waits for a task worker when it checks the connection to a repository you add or when you check its connectivity, fetch a file from it, or view its commits: after the time set by the new `INFRAHUB_BROKER_RPC_TIMEOUT` setting (120 seconds by default) the request now fails with an error instead of waiting indefinitely, and if no worker answers while you add a repository, Infrahub removes it so that you can add it again.
- Changed the number pool details page to list the pool's ranges in the order the pool fills them, with how much of each is used, next to a table of the numbers in the selected range that shows the node holding each one, its branch and whether the pool allocated it or a user provided it. The table can be filtered by source and by branch.
- Added a header to the number pool details page. It shows whether the schema manages the pool and what the pool allocates to. Its Actions menu disables Edit, Groups and Delete on pools that the schema created.
- Changed the number pool form so that creating a pool sets its node, number attribute, optional allocation scope and several weighted ranges, each of which can leave its start or end empty, in one save, and editing a pool changes its name, description and ranges while its node, attribute and scope stay read-only.
- Infrahub now refuses a schema change that renames a kind, by its name or its namespace, or renames an attribute, while a number pool allocates numbers for it. A number pool refers to its kind and its attribute by name, so the rename left the pool referring to a kind or an attribute the schema no longer has. The error names each pool that blocks the rename. Infrahub also refuses a schema change that makes such a kind inherit from another generic, because the objects of the kind are migrated as for a rename.
- A Git repository import now fails, and sets the branch to an import error, when an entry in `.infrahub.yml` cannot be used: a schema path that does not exist, a schema directory that contains no `.yml`, `.yaml` or `.json` file, or a Jinja2 transform whose template file is missing, is empty, is not UTF-8 text, cannot be parsed or is outside the repository. Previously the import skipped a schema path with a warning and continued, and registered the Jinja2 transform, so the template problem appeared only when an artifact was generated. After the upgrade, the next import of a branch whose `.infrahub.yml` has one of these entries shows an import error, and none of that import is applied until the entry is fixed.
- Rewrote the key concepts documentation with concise explanations, infrastructure examples, and diagrams.
- Number pools that allocate for the same unique attribute can no longer have overlapping ranges, because each pool now offers only the numbers its own records leave free: saving an overlapping range is refused, and for pools whose ranges already overlap, attach the numbers in the overlap to one pool by saving each object with its number as `value` and that pool as `from_pool`, then change the ranges of the other pool so they no longer overlap.
- Clarified the description of the `default_branch` attribute on repositories. It now states that the value is the remote branch Infrahub maps onto its own default branch, and that it does not have to be the remote's default branch.
- Reduced the number of database queries the repository sync runs when reading each branch's commit and internal status. The read now costs a small fixed number of queries for the repository nodes plus one query per 100 branches, instead of one query per branch.
- Changed the default of `INFRAHUB_SECURITY_SSO_ACCOUNT_NAME_FALLBACK` (`security.sso_account_name_fallback`) from `true` to `false`, in the application and in the shipped `docker-compose.yml`, so a first SSO login no longer claims an existing unlinked account whose name matches the display name from the identity provider; while the setting is enabled, each Infrahub process now logs a warning when it loads its configuration. If some existing accounts are not yet linked to an SSO identity, set the value to `true` until those users have logged in once: otherwise their first SSO login creates a new, separate account, or fails when neither their display name nor their email is available as an account name. See [How to migrate off the SSO account-name fallback](https://docs.infrahub.app/release-notes/deprecation-guides/sso-account-name-fallback).
- **Breaking:** Changed the format of the `trace_id` log field of the API server from a `0x` hexadecimal number without leading zeros, for example `0xaf7651916cd43dd8448eb211c80319c`, to the 32-character form that Tempo and Grafana use, for example `0af7651916cd43dd8448eb211c80319c`. Update the log queries and alerts that read `trace_id`.
- Reduced the load that the user checks of a proposed change put on the API server, which grew with the square of the number of members in the group that a check definition targets.
- Upgraded the GraphQL sandbox to GraphiQL 6, which replaces the Explorer pane with a query builder, adds operation collections, response views (JSON, tree and table) and display settings, and shows the HTTP status, duration and size of each response.
- Updated the frontend `zod` validation library to 4.6.7.
- Merging a branch, through the `BranchMerge` mutation, `branch.merge` in the Python SDK or a proposed change, is now refused when the last import of a repository on that branch failed or has not completed. The branch stays open, and the error names each repository and how to clear it: push a fix, run "Reimport current commit" or set the repository to inactive on the branch for a failed import, or run "Reimport current commit" for an import that does not complete. ([#10498](https://github.com/opsmill/infrahub/issues/10498))
- A branch created in Infrahub with "Sync with Git" turned off no longer receives commits when a branch with the same name is later created in a connected Git repository, whether or not branch import rules are configured. Infrahub used to import commits from that Git branch into the Infrahub branch, although merging the branch never sent its changes back to Git. After the upgrade, such a branch keeps the last commit it imported and receives no new ones. ([#10684](https://github.com/opsmill/infrahub/issues/10684))
- Editing a repository's `.infrahub.yml` no longer regenerates every artifact and re-runs every Generator in that repository. The manifest used to be part of every Transformation's and Generator's dependency closure, so a comment-only edit, or an entry belonging to an unrelated definition, re-rendered everything; a manifest edit now affects only the definitions whose own configuration it changed, unless a definition still falls back to regenerating on any file change or names `.infrahub.yml` under its `watch.files`. On the first import after upgrading, fingerprints are recomputed for Python Transformations, Generator definitions, and Python-Transformation-backed artifact definitions, which regenerates their artifacts, re-runs those Generators once, and recomputes once every computed attribute backed by a Python Transformation. ([#9643](https://github.com/opsmill/infrahub/issues/9643))
- Improved rendering performance of the proposed change diff view: offscreen diff cards skip layout and paint while scrolling large diffs.

**Fixed**

- Fixed choosing another object of the same kind from the breadcrumb of the object you are viewing, which opened that object on its details tab instead of the tab you were on.
- Fixed the artifact checks of a proposed change crashing with `httpx.PoolTimeout` and staying in progress when the artifact definition targets about a thousand objects.
- Fixed the node events Infrahub emits for the peers of a relationship change. A peer reached through several changed relationships now receives one event instead of one per relationship. Adding or swapping a one-cardinality peer records the protection, owner and source of the new edge, removing one keeps the removed parent, and a peer that holds the mutated node as its parent names it as parent and root node.
- Fixed long attribute and relationship labels on the object details and convert views wrapping onto several center-aligned lines or overlapping the value: a long label now ends with an ellipsis, and hovering it or moving to it with the keyboard shows the full label in a tooltip.
- Fixed the `@expand` directive being ignored when the node it annotates is selected through a named fragment (for example `edges { ...EdgeFields }` with `node @expand` inside `EdgeFields`); the node's attributes are now expanded the same way as when the selection is written inline.
- Fixed one Git branch that failed to synchronize preventing the other branches of the same repository from updating on the other workers, and one failing repository stopping the synchronization of the repositories after it.
- Fixed an account's global permissions changing before a branch is merged, when the members of an account group, the roles of a group or the global permissions of a role were changed on that branch. Global permissions and the roles listed at login now come from the default branch, whatever branch the request is sent to.
- A repository whose default branch is not Infrahub's own default branch could intermittently be read on the wrong branch. Once a worker had cloned the repository, later operations on that worker - artifact generation, transforms, generators, computed attributes and proposed change checks - fell back to Infrahub's default branch instead of the repository's configured default branch. Depending on the remote, this produced output built from the wrong branch's files or a failure naming a branch that was never configured. The configured default branch is now resolved every time the repository is accessed, so all workers behave the same whether or not they already had a local copy.
- Focusing the Infrahub logo in the sidebar with the keyboard now shows the full focus ring: a border in the focus colour with space between it and the logo.
- Fixed a schema load taking the `number_pool_id` of a NumberPool attribute from the loaded file: the load now ignores it with a warning, so a schema exported from another instance gets its own number pools instead of pointing to pools that do not exist.
- `RelationshipRemove` now refuses to remove a node whose own side of the relationship is mandatory with a single peer, instead of leaving that node without the peer its schema requires.
- Fixed Python computed attributes that could stay empty, and artifacts that could be missing, after you added a read-write repository. When the periodic Git synchronization imported the new repository first, it imported the objects before it recorded the repository's commit, so the computed attribute and artifact tasks failed and did not run again.
- Computed attributes, display labels, human-friendly ids and Profile refresh no longer recompute twice for a change made on a branch that carries its own schema. The duplicate work appeared once two or more branches differed from the default branch, and it was most visible on a rebase, where every replayed node was processed twice. The stored values were always correct.
- Improved performance for queries that look up nodes with the top-level ids filter
- Fixed a branch merge being recorded against an external repository even when the remote rejected the push (for example on a protected branch); the rejection now fails the repository merge task with an error describing it, and Infrahub keeps the last commit the remote actually accepted.
- A branch merge that Infrahub refuses for a reason you can fix, such as unresolved conflicts, a failed repository import or a repository that is not synchronized, no longer shows a Python traceback in the task log. The log keeps the message that explains why the merge was refused.
- A branch merge that is refused because an earlier merge failed now says that an administrator must recover that merge, instead of reporting a merge in progress. A merge refused because the remote of a repository rejects the credentials now logs the error output of Git as a warning in the task log.
- A Python transform or check whose `class_name` is not defined in its module now fails the branch import with a message that names the entry, instead of being skipped silently and having its existing definition deleted from Infrahub.
- Fixed converting an object to another kind freeing a number it held from a number pool, which let the pool hand the same number out again. The pool keeps accounting for the number when the new kind is one the pool tracks, such as another kind inheriting from the generic the pool is attached to.
- Fixed a read-only repository that stayed on its old commit when its `ref` or `commit` changed through an upsert, for example with `infrahubctl object load` or the SDK `save(allow_upsert=True)`: the upsert now pulls and imports the new target, as an update does.
- Fixed Infrahub's default branch no longer receiving commits from a repository when branch import rules are configured and the repository's default branch has a different name, such as develop, that no rule matches.
- Viewing the files changed in a branch no longer fails when that branch contains a repository that was added or synced for the first time while the branch was open, or one whose commit was removed. Such a repository has no earlier commit to compare against, and the resulting error stopped the entire comparison, so the files changed in the branch's other repositories were not listed either. A repository with nothing to compare against is now left out of the list, and the remaining repositories report their changed files as usual.
- Fixed a failed import of a repository branch showing in the repository's task log on the default branch instead of on the branch that failed.
- The scheduled repository sync now reads a repository's operational status from the database instead of always seeing `unknown`, so a repository that is online again gets tagged when a sync fails.
- A Python computed attribute that shares its transform with another computed attribute is now recomputed automatically. The automations were indexed by transform name, so out of several attributes fed by one transform only one got an automation. A sibling attribute on another kind was then never refreshed when a node changed, and kept the value of its last successful compute. Each attribute now gets its own automation for a change to a node of its own kind, and the transform's query automations cover every attribute it feeds. A schema change on a branch now also recomputes the Python computed attributes that branch shares with the default branch.
- Fixed the count at the bottom of a table being covered by the other footer cells when you scroll the table horizontally.
- Telemetry snapshots are now still produced and sent when Infrahub cannot read the database host's memory and processor information; that field is reported as empty instead.
- Fixed the `infrahub-testcontainers` pytest plugin losing the performance results after one failed upload: it now retries the upload up to 3 times, a number that `--performance-result-retries` changes.
- Fixed stray style names being written onto every row of a tree or a list. Internal state names from the underlying component library were passed through as if they were style names, which changed nothing visually but could have collided with a real style name added later.
- Fixed the GraphQL sandbox ignoring the request headers entered in its Headers tab.
- Fixed the GraphQL sandbox requiring a page reload once the session token expired.
- Removing the last object file from a repository, or clearing the `objects:` list in `.infrahub.yml`, now deletes the objects that file defined. Previously an import pass that ended up tracking no objects skipped the cleanup entirely, so those objects stayed in the instance as orphans and the repository's tracking group kept listing them. Removing one object file among several already worked. The empty case also covered removing every object file except those that define Generator actions or trigger rules, since those are imported in a later pass with a tracking group of their own.

  Objects left orphaned by earlier versions are deleted on the first import after upgrading. If you worked around this by removing object files one at a time, or by keeping a placeholder object file, neither is needed any more.

  An object that cannot be deleted because another node still references it through a mandatory relationship no longer aborts the rest of the cleanup. Every other object is still removed, the failures are reported together, and the objects that could not be deleted stay in the tracking group so the next import retries them. The import itself continues: menus, checks, Generators and artifact definitions are still applied, and the failed deletions are reported as a warning on the import task rather than failing the repository sync. ([#10134](https://github.com/opsmill/infrahub/issues/10134))
- Fixed GraphQL queries silently returning missing or null values when a selection reached a field through a fragment nested inside an inline fragment, or selected the same field more than once under one response key through repeated fields, sibling fragment spreads, or sibling inline fragments. The backend now reads the union of everything the query selects at every nesting depth instead of dropping or overwriting the overlapping branches; a query whose dropped field was non-null previously failed outright with a "Cannot return null for non-nullable field" error. ([#10653](https://github.com/opsmill/infrahub/issues/10653))
- Fixed the IPAM tree crashing with "Invalid array length", or hiding prefixes, when scrolling loaded more prefixes. ([#10719](https://github.com/opsmill/infrahub/issues/10719))
- Fixed the list view search and the IP prefix and IP address filters returning no result when an IPv6 value was typed with leading zeros or in its full form. ([#10926](https://github.com/opsmill/infrahub/issues/10926))
- Fixed schema loads accepting malformed human-friendly ID paths and reporting unclear errors for invalid stored uniqueness constraints. ([#10942](https://github.com/opsmill/infrahub/issues/10942))
- Infrahub now refuses a Number attribute value below -9223372036854775807 or above 9223372036854775807 with a validation error; such values previously caused a server error, except -9223372036854775808, which was stored. ([#11247](https://github.com/opsmill/infrahub/issues/11247))
- Fixed time-range diffs of the default branch reporting a node deleted by a branch merge as updated instead of removed. ([#11344](https://github.com/opsmill/infrahub/issues/11344))
- Fixed time-range diffs of the default branch reporting the first value ever, instead of the value at the start of the range, as the previous value of a deleted node. ([#11345](https://github.com/opsmill/infrahub/issues/11345))
- Fixed time-range diffs of the default branch reporting the first value ever, instead of the value at the start of the range, as the previous value of a property of a removed relationship peer. ([#11358](https://github.com/opsmill/infrahub/issues/11358))
- Fixed a GraphQL query that selects the same top-level field more than once (for example `BuiltinTag { count }` alongside `BuiltinTag { edges { ... } }`) returning only the first occurrence's selection and dropping the rest. When a dropped selection held a non-null field the whole response failed with a "Cannot return null for non-nullable field" error. The selections from every occurrence are now merged into one result. ([#5430](https://github.com/opsmill/infrahub/issues/5430))
- Fixed proposed change Generator checks that failed when a Generator instance remained after its target object was deleted. ([#6293](https://github.com/opsmill/infrahub/issues/6293))
- Fixed the synchronization of a Git branch whose history was rewritten and force-pushed: the branch now follows the new remote history and its objects are imported again with no user action, instead of the repository going to the error status with a merge conflict that did not exist. ([#6299](https://github.com/opsmill/infrahub/issues/6299))
- Common Git repository import failures caused by the repository's content, such as an invalid schema, object file or query, are now logged once as a readable message that names the failing entry and file in `.infrahub.yml`, without a Python traceback. A failure the import does not recognise is still logged once with its traceback. A failed import of one branch no longer stops the import of other branches, except for a connection or credential error, which still stops the repository's sync for that cycle. ([#7498](https://github.com/opsmill/infrahub/issues/7498))
- Fixed the repository sync logging "New commit detected" every minute for a branch it does not import; the sync now logs "New commit detected" or "New branch detected" at info level only for a branch it is about to try to import, and logs at debug level the branches it skips because the repository is staging or inactive, or because their Infrahub branch does not sync with Git or does not accept a commit. ([#8859](https://github.com/opsmill/infrahub/issues/8859))
- Fixed a merge of a branch that syncs with Git, through a Proposed Change or directly, that could skip the Git merge or put commits removed by a force push back in the Git repository, when Infrahub had not yet recorded the latest commit of the branch. Infrahub now refuses the merge until it records the latest commit pushed to the branch and to the branch it merges into. The branch stays open, so you can merge again after the next synchronization. When the Git repository is rewritten during the merge, Infrahub pushes nothing, keeps the merge in the push queue of the repository, and records the cause on the repository. ([#9499](https://github.com/opsmill/infrahub/issues/9499))
- Branch merge and proposed change review events are now emitted on the default branch, so webhooks scoped to the default branch reliably match them regardless of which branch triggered the change. ([#9761](https://github.com/opsmill/infrahub/issues/9761))
- Fixed read-only repositories failing to follow a tracked tag that was moved upstream: an import either failed or kept the commit the tag used to point at, and workers other than the one running the import could not pick up the new commit. ([#9826](https://github.com/opsmill/infrahub/issues/9826))

**Housekeeping**

- Consolidated the frontend on a single linter and formatter. `frontend/packages/ui` and `frontend/packages/graph` used `oxlint` + `oxfmt`, which nothing in CI ever ran, while `frontend/app` used Biome; both packages had therefore been unchecked since they were created. Biome now owns the whole `frontend/` pnpm workspace from one root configuration, and the `frontend-lint` CI job gates the app and the packages in a single step.
- Fixed intermittent failures in the frontend unit test job. A dependency discovered during a test run made the page reload, which discarded module mocks and failed whichever test file was running at the time. Those dependencies are now loaded before the run starts, including ones owned by other packages in the frontend workspace, which the previous test configuration failed to resolve.
- The BLE (flake8-blind-except) ruff rule is now enforced — blind `except Exception` handlers are either narrowed to the specific exception types they guard against or carry an explicit justified `# noqa: BLE001`.

## [Infrahub - v1.11.10](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.10) - 2026-10-30

### Security

- Updated the base Python version of the Infrahub container image and the development environment from 3.14.7 to 3.14.10, so the `pip` bundled in the image no longer ships a `certifi` version affected by GHSA-6q48-6c7w-9gw2.

### Added

- Added Redis Sentinel support: when `INFRAHUB_CACHE_URL` is set to a `redis+sentinel://` URL, Infrahub connects to the Sentinel nodes and follows a failover of the Redis master, so a `redis-sentinel-proxy` is no longer needed. See [High availability](https://docs.infrahub.app/deploy-manage/install-configure/production-deployment/high-availability). ([#9449](https://github.com/opsmill/infrahub/issues/9449))
- Added the `INFRAHUB_BROKER_QUEUE_TYPE` setting to declare the durable RabbitMQ queues as quorum queues, so that they stay available when a node of a RabbitMQ cluster stops.

### Changed

- **Breaking:** Raised the Redis requirement to version 6.0 or later, or a Redis-compatible service that supports the `HELLO` command, because Infrahub now opens every Redis connection with `HELLO`, which Redis 5.0 and earlier reject. ([#9449](https://github.com/opsmill/infrahub/issues/9449))
- Changed the error message for a GraphQL query with a syntax error to start with "Query is not valid, ". ([#11232](https://github.com/opsmill/infrahub/issues/11232))
- Removed the concurrency limit from the `clean-up-deadlocks` task, so a run that never finishes, for example after a task worker restarts while the run is starting, no longer stops later runs from removing locks left behind by inactive task workers.

### Fixed

- Fixed creating or upserting an object whose computed attribute reads a related object given by a human-friendly ID: a related object that does not exist is now reported by name instead of causing an internal server error that clients retried for several minutes, and a related object of a generic kind given with its specific kind is now found. ([#11018](https://github.com/opsmill/infrahub/issues/11018))
- Fixed repository sync ignoring a changed `transformation` on an existing artifact definition in `.infrahub.yml`, which also deleted the artifact definition when its Transformation was renamed. ([#11036](https://github.com/opsmill/infrahub/issues/11036))
- The Git repository sync, deadlock clean-up and failed-merge detection tasks, which run every minute, no longer store a result in the task manager database and the cache for each run. ([#11166](https://github.com/opsmill/infrahub/issues/11166))
- Fixed filters, search, and finding an object by name or human-friendly ID on a branch matching objects by a value that the branch had already changed. ([#11218](https://github.com/opsmill/infrahub/issues/11218))
- Fixed an invalid GraphQL query, a GraphQL query with a syntax error, a webhook rename to an existing name and the deletion of the default IP namespace returning HTTP 500 instead of 422, which made the SDK retry a repository import for 5 minutes before it failed. ([#11232](https://github.com/opsmill/infrahub/issues/11232))
- Fixed proposed change checks that stayed in progress forever, and blocked the merge, when one of their runs failed or timed out. ([#11277](https://github.com/opsmill/infrahub/issues/11277))
- Fixed GraphQL queries that request two or more custom root fields in one request, such as two `InfrahubResourcePoolUtilization` fields, failing with a database read error or hanging.
- Fixed certain schema changes being accepted when data violates them: a schema load or a branch merge is now refused when existing values fall outside a Number attribute's new `min_value`, `max_value` or `excluded_values`, outside a schema-defined number pool's new `start_range` or `end_range`, or no longer match a relationship's new `peer` or a hierarchical node's new `parent` or `children`.
- Fixed merges that re-run a Generator set to execute after merge leaving an unused diff stored in the database. Upgrading deletes the diffs that earlier merges left behind.
- Fixed repository sync ignoring a changed `class_name` on an existing Python Transformation in `.infrahub.yml`.
- Fixed repository sync ignoring a changed `class_name` on an existing check definition in `.infrahub.yml`.
- Fixed repository sync ignoring added, changed or removed `targets` on an existing check definition in `.infrahub.yml`, and made the sync fail with an import error when the target group does not exist.
- Fixed task results accumulating in Redis without ever expiring: results now expire two days after they are written.
- Fixed the "Documentation" links in the web interface for built-in object types, such as artifacts, generators, transformations, repositories and accounts: they pointed to documentation pages that no longer exist. Added "Documentation" links to built-in object types that had none, such as check definitions, trigger rules, groups, webhooks, resource pools and permissions. When a schema's `documentation` value starts with `http`, the "Documentation" link now opens that URL directly, instead of the documentation home page or a broken link; any other value still opens that path in the documentation that ships with Infrahub. Links to the documentation that ships with Infrahub now end with a trailing slash, so they open the page directly instead of through a redirect that fails when Infrahub runs behind a reverse proxy.
- Fixed the `infrahub-testcontainers` package starting Neo4j 2025.10.1 instead of 2026.05.0, the version that Infrahub ships with, in test runs of Infrahub Community that do not set `NEO4J_DOCKER_IMAGE`.
- Fixed the scroll bars of tables, such as object lists, being hidden behind the table's pinned header, footer and actions column, which stopped mouse users from scrolling.

### Housekeeping

- The container image build now installs the `uv` version defined in `define-versions.yml` (0.13.6) instead of the latest release, and stops when no version is given.

## [Infrahub - v1.11.9](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.9) - 2026-10-22

### Security

- Updated `certifi` to 2026.10.19, which removes the emSign root certificates after intermediates were revoked due to key compromise (GHSA-6q48-6c7w-9gw2).

### Changed

- In the GraphQL schema, the `node_metadata` field of the `NestedEdged` type of every generic can now be null: its type changes from `InfrahubNodeMetadata!` to `InfrahubNodeMetadata`, as it already was on the `NestedEdged` types of node kinds. Teams that generate client types from the GraphQL schema will see `node_metadata` on these types as optional and must handle a null value. ([#11100](https://github.com/opsmill/infrahub/issues/11100))
- Artifacts and Generators that read a relationship with a filter are no longer regenerated when a change only affects related objects that the filter excludes.

### Fixed

- Fixed GraphQL queries failing with a "Cannot return null for non-nullable field" error when they requested `node_metadata` on a relationship whose peer kind is a generic. An empty cardinality-one relationship, such as the `parent` of a node at the top of a hierarchy, now returns `node` and `node_metadata` as null. The `ancestors` and `descendants` of a hierarchical node now return the `node_metadata` of each node. ([#11100](https://github.com/opsmill/infrahub/issues/11100))
- Fixed proposed changes that showed data conflicts on the fingerprint of Generator and Transformation definitions after another branch with Git changes was merged.

## [Infrahub - v1.11.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.8) - 2026-10-19

### Added

- Added support for Python 3.15 to the `infrahub-testcontainers` package.

### Changed

- Changed proposed-change and post-merge regeneration to follow a `display_label` or `human_friendly_id` read on a generic through the value that each implementation defines or inherits, instead of selecting every target when the generic defines none.
- Changed proposed-change and post-merge regeneration to select only the targets that read a changed node when the query reaches that node through an inline or named fragment, instead of every target of the definition.
- Changed proposed-change and post-merge regeneration to select only the targets that read a changed node when the query reads its kind both at the root and through a relationship, instead of every target of the definition.

### Fixed

- Fixed GraphQL queries ignoring the fields read through a named fragment used inside another fragment, such as `... on InfraDevice { ...DeviceInterfaces }`. When such a field changes, artifacts and Generators that read it are now regenerated and computed attributes based on a Python transform are recomputed. Object permissions are now checked on these fields.
- Fixed artifacts and Generators not being selected after a change to an object whose kind was added to a generic after their query was saved, when the query reads that generic. The kinds a query reads are now taken from the query text each time a change is checked, instead of from the list stored when the query was saved. The `models` attribute of a GraphQL query is still computed only when the query text is saved, so it can miss kinds the query reads, such as a kind added to a generic afterwards. It no longer affects which artifacts and Generators are regenerated.
- Fixed artifacts not being regenerated and Generators not being run after a change to a field that their query reads only inside a fragment on a generic.
- Fixed the `infrahub-git-credential` helper returning "No such command 'erase'" in the task log after Git fails to authenticate with a remote repository.
- Fixed the scheduled job that revokes approvals on updated proposed changes (Enterprise) checking every proposed change, including merged, closed and canceled ones, instead of only the open ones. On an instance with many old proposed changes, the job started one whole-graph scan per proposed change every 10 minutes and could make the database too slow to log in.

## [Infrahub - v1.11.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.7) - 2026-10-14

### Fixed

- Concurrent creates of the same IP address on a branch other than the default branch now leave a single IP address when the schema declares a uniqueness constraint on it. The extra creates are rejected with the uniqueness error, as they are on the default branch. ([#11059](https://github.com/opsmill/infrahub/issues/11059))
- Fixed the "info" severity badge in task logs having the same color as the "warning" badge; it is now blue.

## [Infrahub - v1.11.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.6) - 2026-10-13

### Changed

- Post-merge and proposed-change regeneration now regenerate only the affected members when a Generator or artifact query reads a `display_label` or `human_friendly_id` built from a related node's attribute and that related node changes. A query that does not target unique objects, or whose `display_label` or `human_friendly_id` path cannot be resolved, still regenerates every member of the definition.
- Post-merge regeneration now narrows to the affected members when the changed data is read through a relationship (for example an owner's name rendered by an artifact, or an interface's field on a device), instead of regenerating every member of the definition. Changes that cannot be attributed to specific members unambiguously still regenerate the whole group.

### Fixed

- Fixed artifacts and Generators not being regenerated after a merge or in a proposed change when the change was to a field their query filters on, such as moving an object to the related node the query selects by. ([#11024](https://github.com/opsmill/infrahub/issues/11024))
- Fixed Generators not running in a proposed change or after a merge when the only change was to a Profile of a kind their query reads.

## [Infrahub - v1.11.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.5) - 2026-10-08

### Security

- Updated `PyJWT` to 2.15.0, `urllib3` to 2.8.0, `oauthlib` to 4.0.0, `dulwich` to 1.2.9, `fsspec` to 2026.6.0 and `GitPython` to 3.1.62 to fix published security vulnerabilities, including the critical PyJWT vulnerability [CVE-2026-102268](https://github.com/advisories/GHSA-ffc3-869f-jxw9). ([#10803](https://github.com/opsmill/infrahub/pull/10803), [#10903](https://github.com/opsmill/infrahub/pull/10903), [#10837](https://github.com/opsmill/infrahub/pull/10837))

### Fixed

- Fixed the repository import getting stuck in an error state when a single commit removed a GraphQL query from `.infrahub.yml` and also removed the Transformations or Generator definitions that used it, or pointed them at another query. A query removed from `.infrahub.yml` is now deleted even when the repository declares no other queries. Deleting a removed Transformation also deletes every artifact definition that references it, including artifact definitions created outside the repository, along with their artifacts. ([#10109](https://github.com/opsmill/infrahub/issues/10109))
- Fixed a node getting a duplicate uniqueness constraint when an existing constraint lists its human-friendly ID fields in a different order. Infrahub removes the duplicate from an existing schema the next time that node's schema is loaded. ([#10793](https://github.com/opsmill/infrahub/issues/10793))
- Fixed a slow creation, update and refresh of objects when many objects use the same Profile.
- Fixed a slow deletion of a Profile, and a slow removal of objects from a Profile, when many objects use the Profile.
- Fixed a slow update of a Profile with many objects, when the update does not include `related_nodes` or `related_templates`.
- Fixed branch creation and other high-priority tasks waiting behind a large backlog of background tasks before they start.
- Fixed missing related objects in large GraphQL queries, when objects share related objects and the relationship has more rows than the query size limit (5,000 by default).
- Fixed searches returning no results when the search text starts or ends with a space, for example after pasting it from another application. This affects the search box on node list views and on the branches, tasks, proposed changes and IPAM namespaces pages. It also affects the search in relationship fields on create and edit forms, and in the relationship filter of list views.

## [Infrahub - v1.11.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.4) - 2026-10-01

### Security

- Prevented Infrahub from serving an artifact file that no longer matches its checksum, for example after it was modified in the object storage; reading it now returns an error asking to regenerate the artifact, and Re-generate on the artifact page stores a correct copy.

### Added

- Added `INFRAHUB_STORAGE_TLS_INSECURE` to skip certificate validation of the S3 endpoint, and a per-destination `tls_insecure` setting that does the same for log-forwarding syslog servers (Enterprise), for test environments.
- Added the `infrahub db delete-diffs` command, which deletes the stored named diffs that are not frozen, and with `--include-branch-diffs` the unfrozen branch diffs too, for every branch or for a single branch with `--branch`.

### Changed

- Changed the node events sent when a branch is rebased: every rebase now replays all of the branch's own changes onto the new base, and the default branch's changes only for the object types whose schema the branch changed, instead of every change made on the default branch since the branch was created or last rebased. Webhooks and action rules receive an event for each of the branch's changes on every rebase.

### Fixed

- Fixed the file and artifact diffs displaying the lines around hidden unchanged lines as if they were adjacent; a separator now marks each block of hidden lines and expands it on click. ([#6938](https://github.com/opsmill/infrahub/issues/6938))
- Fixed IPHost, IPNetwork and IPAddress attribute values not being normalized when updated. This broke value filters and the Schema Integrity check on proposed changes, and let an update bypass a uniqueness constraint when the address was written without its prefix length ([#10616](https://github.com/opsmill/infrahub/issues/10616))
- Fixed a branch with conflicts against the default branch being unable to leave the `NEED_UPGRADE_REBASE` status: a rebase now accepts a conflict on an attribute once it is resolved in favor of the branch, and its error says, for each conflict that still blocks it, whether to resolve it in favor of the branch or to update the data.
- Fixed a conflict going unreported when the default branch changed a relationship before a branch first changed the same relationship.
- Fixed a display label or Jinja2 computed attribute that fails to render on one node preventing the refresh of the other nodes processed with it.
- Fixed diff updates and branch rebases slowing down sharply when the diff contains a node related to thousands of objects, such as an IP namespace after a bulk IP address import.
- Fixed diff updates on large branches stalling for tens of seconds after the diff was computed and storing a copy of the whole diff in Redis.
- Fixed display labels, human-friendly IDs and computed attributes taking too long to refresh on kinds with many nodes after their schema definition or their Python transform changed.
- Fixed rebasing a branch after large changes on the default branch taking a long time and exhausting worker memory.
- Fixed rebasing a branch with changes of its own not releasing the branch-agnostic attribute and relationship values of objects deleted on the default branch, which kept counting towards uniqueness constraints and kept resource pool values allocated.
- Fixed recreating a branch's diff, as happens after a rebase, reading the whole default branch side of the previous diff. A diff stored by an earlier version can hold every change made on the default branch since the branch was created, so the refresh could take minutes, exhaust worker memory and hold up a merge of the branch.
- Fixed refreshing a computed attribute for a whole kind skipping some nodes when the kind is sorted on that computed attribute.
- Fixed startup failing on a CA bundle setting left empty, such as a blanked `INFRAHUB_TLS_CA_BUNDLE` or `AWS_CA_BUNDLE` variable; an empty value is now read as unset
- Fixed the "Infrahub is busy" notice closing early, and reopening instead of updating, when several retried requests completed within half a second of each other
- Fixed the artifact and file viewers showing "Sorry, no data found." when the content could not be loaded; they now show the reason returned by the server.
- Fixed the diff of a branch showing a relationship peer as added on the default branch when the default branch had added and removed it again before the branch changed that relationship.
- Fixed the diff of a branch without changes of its own collecting every change made on the default branch since the branch was created, which made updating its diff and rebasing it slow and could exhaust database memory.
- Fixed the diff update of a branch with tens of thousands of changed nodes taking many minutes longer than its data justifies: the diff is now calculated one chunk of changed nodes at a time, saved in batches that cost the same at any size and are written several at a time (bounded by the new `diff_save_concurrency` database setting), and its display labels are read from the nodes instead of being recomputed for every changed node.
- Fixed the warning logged when an artifact or Generator definition regenerates every target, which always blamed target uniqueness; it now states the actual reason, and the reason is also logged after a merge.
- Fixed the web UI being replaced by a raw JSON error body when the server is shedding load: a page load is no longer shed, so opening or refreshing Infrahub under heavy load reaches the app and its own retry handles the requests the page then makes.
- Sped up artifact generation and transform rendering when the GraphQL query returns a large response.

## [Infrahub - v1.11.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.3) - 2026-09-23

### Added

- Added an `X-Infrahub-Admission: shed` marker header to load-shed `429` responses, exposed to cross-origin clients along with the `Retry-After` hint, so a client can tell an admission shed from any other `429`.
- Added the `INFRAHUB_TLS_CA_BUNDLE` setting, a CA bundle given as a file path or as PEM text and trusted by every component that opens outbound TLS connections, including git repositories and S3 object storage, so Infrahub can run against a private certificate authority without a custom Docker image; git also gained `INFRAHUB_GIT_TLS_CA_FILE` and `INFRAHUB_GIT_TLS_INSECURE`. Every component CA setting now accepts PEM text as well as a path and is validated at startup. The clients the task worker and the git credential commands use to reach the Infrahub API now follow these settings as well, instead of the `INFRAHUB_TLS_CA_FILE` and `INFRAHUB_TLS_INSECURE` environment variables read by the Python SDK.
- Added the `infrahub db reset` command to delete all data from the graph database and the task manager database, resetting whichever of the two the current environment is configured for, for example to start over on a development or test deployment without recreating the containers.

### Changed

- **Breaking:** `POST /api/schema/load` and `POST /api/schema/check` now return one `422` entry per offending field, located on that field through `loc` and carrying the value received there in `input`. Previously a rejected schema produced a single entry located at the schema index, with every violation concatenated into its `msg` and the whole submitted schema as its `input`. A consumer that read the joined message text now sees only the first violation there and must read `loc` and `input` on each entry instead. The wording of each reason, the set of payloads accepted or rejected, and the offline `validate_schema` output are unchanged. ([#10601](https://github.com/opsmill/infrahub/issues/10601))
- Changed the web UI to wait and retry when the server is shedding load, telling the user how long the wait is, instead of failing the request immediately.
- Replaced the per-lab documentation pages under Learn with a single "Infrahub Labs" link to the labs catalogue at [docs.infrahub.app/labs](https://docs.infrahub.app/labs), which describes every lab in full and also covers labs hosted for partners and the community.
- Updated the homepage's Getting Started "Schema Library" card to point to the Infrahub Marketplace instead of the GitHub schema-library repository.
- Upgraded Prefect to `3.8.6` (from `3.7.5`) and `prefect-redis` to `0.2.15` (from `0.2.14`). The first start after this upgrade can take longer than usual while the task manager database is updated, on deployments with a long task history. Later starts are unaffected.

### Fixed

- Branch-agnostic attributes and relationships on branch-aware objects no longer stay reserved forever after the object is deleted. Previously the value was left in place for every branch, so it still counted towards uniqueness constraints and an allocated resource pool value stayed allocated to an object that no longer existed. An attribute's value is now released once no branch can still read its object, and a relationship's once no branch can still read both of its peers; released pool values become allocatable again. Upgrading releases the values earlier versions left behind. See [Branch-agnostic data](https://docs.infrahub.app/branches/branch-agnostic-data). ([#9762](https://github.com/opsmill/infrahub/issues/9762))
- Fixed a repository's first import failing when its objects declared Generator actions or trigger rules referencing a Generator definition from the same repository; those objects are now imported after the definitions they depend on, so the import succeeds on an empty instance without a manual reload. ([#10063](https://github.com/opsmill/infrahub/issues/10063))
- The Tasks tab of a Generator instance now lists the flow runs that executed the Generator for that target, so an instance's execution history is visible from the instance itself. ([#10107](https://github.com/opsmill/infrahub/issues/10107))
- Fixed the sidebar menu hiding your object items on a short window. The lower (built-in) menu no longer takes all the vertical space: both menu sections now shrink and scroll, and the object section keeps a minimum height so its items stay reachable at any window size or zoom level. ([#10158](https://github.com/opsmill/infrahub/issues/10158))
- Running a Generator definition whose targets include a failing member now reports which targets failed and how many succeeded, instead of collapsing into a single opaque failure. ([#10199](https://github.com/opsmill/infrahub/issues/10199))
- Attaching or removing a child now reports the change on the hierarchical parent's `children` relationship, instead of on its `parent` relationship. A Python transform computed attribute or an action rule that matches `children` now reacts. Deleting a node that has both a parent and a child now reports both sides. ([#10485](https://github.com/opsmill/infrahub/issues/10485))
- Fixed repository sync failures reporting only the branch name; the failing step and reason are now included in the error and surfaced in the Tasks tab. ([#10526](https://github.com/opsmill/infrahub/issues/10526))
- Fixed the branch merge mutation reporting a "branch not found" error for a merge that succeeded when automatic branch deletion after merge is enabled. ([#10578](https://github.com/opsmill/infrahub/issues/10578))
- Converting a node that has already been converted now returns a clear not-found error instead of an HTTP 500. ([#10646](https://github.com/opsmill/infrahub/issues/10646))
- Fix refreshing the diff of a proposed change failing with "Cannot find diff" when no diff had been stored yet. A diff update that found the update lock already held assumed the holder had saved a diff, but the queries that read a diff take the same lock only to wait for any update in flight, so the update can now find nothing stored. It calculates the diff itself in that case instead of returning an error.
- Fixed HTTPS clones of repositories whose certificate cannot be verified being reported as a generic error instead of the connection error status and certificate hint.
- Fixed `INFRAHUB_HTTP_TLS_INSECURE` being ignored when a CA bundle was configured alongside it, which made the clients that reach the Infrahub API keep validating certificates. Disabling verification no longer requires removing the bundle first, matching the documented precedence and the behavior of the other components.
- Fixed a long rebase, merge or diff update of a large branch failing with "Cannot release a lock that's no longer owned" after all its work was done: a worker busy on a CPU-heavy step could miss its heartbeat, and the periodic deadlock cleanup then deleted the locks it was still holding. The heartbeat now runs on its own thread, so a worker only looks inactive once it has actually stopped.
- Fixed a merge or schema-update rollback leaving branch-agnostic object, attribute, and relationship timestamps wrong: it could revert the timestamps of an unrelated branch-agnostic change made in the same window, and could clear timestamps it had already restored.
- Fixed large listings slowing down as they page through results: Neo4j planned every page of a paginated database query from scratch because the page bounds were written into the query text, and all pages now share one cached plan.
- Fixed saving the diff of a large branch slowing down as more nodes were written: every batch of diff nodes now costs the same however many nodes the diff already holds.
- Fixed the diff calculation of a large branch re-reading every change on the branch for each page of results: attribute, relationship and property changes are now calculated one chunk of changed nodes at a time.
- Fixed the diff update of a branch with an open proposed change stalling for minutes after the diff was saved when the branch holds tens of thousands of changed objects, which also blocked every other task on that worker for the duration.
- Fixed the display label enrichment of a large diff keeping a worker busy for tens of seconds: the labels are now read from the display labels stored on the nodes instead of being recomputed through a full node object for every changed node.
- In graph traversal results (path and dependency modes), both ends of a hierarchy edge were reported as `parent`. Each end now reports its own side (`children` on the parent end); when the hierarchy does not pin its parent and children kinds, the sides are a consistent best guess.

## [Infrahub - v1.11.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.2) - 2026-09-03

### Fixed

- In Account settings → Preferences, the date format and timezone fields now preview the value that saving would produce, including the organisation default that takes over when a personal override is cleared. The information icon describes the value you are about to save rather than the one already stored. ([#10200](https://github.com/opsmill/infrahub/issues/10200))
- An SSO user's account can be deleted without leaving broken data behind. Deleting an account now also removes its external identities, its API tokens and its refresh tokens, which were left behind before. The ones left by an earlier release are removed on upgrade. ([#10304](https://github.com/opsmill/infrahub/issues/10304))
- Deleting a branch now purges its settled tasks, so a new branch created with the same name no longer inherits the deleted branch's completed tasks. ([#10474](https://github.com/opsmill/infrahub/issues/10474))
- A branch that cannot be refreshed into a worker's in-memory registry no longer aborts the periodic branch refresh. The failure is logged and the remaining branches are still refreshed.
- Artifacts and Generators whose query reads an object's display label or human-friendly ID are now regenerated when a change to a backing field moves that value, instead of being skipped and left stale after a merge.
- Update the in-memory cache for branches after a branch change is saved to prevent the cache diverging from the database. The BranchUpdate mutation and the Prefect task to run database migrations against a branch are both fixed.

## [Infrahub - v1.11.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.1) - 2026-08-31

### Added

- Added the optional INFRAHUB_DB_MAX_CONNECTION_LIFETIME and INFRAHUB_DB_LIVENESS_CHECK_TIMEOUT database settings to protect queries from hanging on pooled connections that a firewall, NAT gateway or load balancer silently dropped while idle
- Traces can now be exported to an OTLP collector that terminates TLS with a private or self-signed certificate. `INFRAHUB_TRACE_TLS_CA_BUNDLE` points at the certificate authority bundle used to verify the collector, and `INFRAHUB_TRACE_TLS_INSECURE` skips verification entirely in test environments. See the [observability documentation](https://docs.infrahub.app/deploy-manage/install-configure/install/observability-stack#exporting-to-a-collector-that-uses-tls) for the supported combinations.

### Changed

- Creating and updating objects is now faster: a mutation reads the peers of the relationships in its payload once, instead of once per validation step, and reading an object together with its relationships no longer costs an extra query for each relationship without a peer. Bulk loads and repeated upserts of unchanged data benefit the most.
- Creating objects from an object template is now faster when the objects it creates share a related object, such as the transceiver model used by every interface of a device template.
- Creating objects from an object template is now significantly faster, and no longer slows down as more objects are created from the same template. Bulk loads from templates, such as loading object files or synchronizing with the SDK, benefit the most.

### Fixed

- Attributes gained when an existing node kind starts inheriting from a generic are now created on pre-existing nodes, including their Profile and Template instances, with NumberPool attributes allocated from the generic's pool. Schema migrations now run kind-update migrations to completion before all other migrations to prevent them from racing each other. ([#9284](https://github.com/opsmill/infrahub/issues/9284))
- Long values in an object table's first column no longer overflow onto the row action menu and the horizontal scrollbar. Table columns are now capped and truncated, with the full value shown on hover. ([#9743](https://github.com/opsmill/infrahub/issues/9743))
- `INFRAHUB_TRACE_INSECURE` now takes effect: the gRPC OTLP trace exporter connects without TLS when it is true (the default), instead of always attempting a TLS connection and failing against plaintext collectors with `StatusCode.UNAVAILABLE`. An endpoint with an explicit `https://` scheme still uses TLS regardless of the setting. ([#9869](https://github.com/opsmill/infrahub/issues/9869))
- Fixed flow runs that stopped being watched for crashes once they entered a retry wait. A run whose process died while waiting out a retry backoff, such as a webhook delivery between attempts, stayed scheduled forever instead of being marked as crashed. ([#10338](https://github.com/opsmill/infrahub/issues/10338))
- Fixed the dropdown option list overflowing its container and hiding option labels when a choice had a long description. ([#10366](https://github.com/opsmill/infrahub/issues/10366))
- The web UI no longer sends you back to the homepage on the default branch when a single refresh of the branch list happens to omit the branch you are working on. The branch is now re-checked against a freshly fetched list before the redirect, so a branch that still exists keeps its page and its selection, while a branch that really was deleted still redirects. If the default branch itself is missing from the deployment, the web UI now shows an error instead of redirecting in a loop. ([#10389](https://github.com/opsmill/infrahub/issues/10389))
- Fixed adding a branch-agnostic attribute to an existing kind writing its edges to the branch the
  schema update ran on instead of the global branch.
- Fixed repositories whose default branch differs from the Infrahub default branch being flipped to the `error` operational status when a task worker synchronized them by pulling instead of checking out a pinned commit. The pull now targets the repository's own default branch instead of the Infrahub branch name, which does not exist on the remote.
- Fixed unbounded memory growth in API server processes: the GraphQL type registry now evicts the previous schema of a branch when its schema changes, instead of retaining every historical GraphQL schema until restart.
- Schema-change recompute scoping now applies to a Python computed attribute whose transform query reads a human-friendly id or display label. Such a read could not be mapped to the schema elements it depends on, so the attribute recomputed on every schema change, across every node of its kind. A derived value built from the kind's own attributes is now scoped to that kind; one that reaches through a relationship still recomputes on any schema change, because its impact cannot be determined.
- Sped up GraphQL query execution by keeping non-mutation requests on the synchronous resolution path. The branch-status middleware previously wrapped every resolved field in a coroutine, which made large read queries — most visibly the GraphQL sandbox's schema introspection — take 10+ seconds and starve other requests handled by the same API worker while they ran.
- The `BranchCreate` GraphQL mutation now rejects a client-supplied `branched_from` value with an error, and the field is marked deprecated. `branched_from` is an internal field managed by the application. The `origin_branch` field, which was already rejected for any value other than the default branch, is now also marked deprecated. An empty string is now rejected for either field instead of being silently accepted, and an explicit `null` on an optional field is treated the same as omitting it.
- Upgrading now repairs nodes left without attribute rows by earlier versions, where an existing node kind that started inheriting from a generic never got rows created for the inherited attributes on its pre-existing nodes. Such nodes read the attribute back as unset, accepted updates that silently persisted nothing, and never matched a filter on its value. The upgrade repairs the default branch and every other branch is repaired when rebased. Profile and Template instances are repaired alongside concrete ones wherever they support the attribute. Rows are created at the time the repair runs: attributes with a default value carry it, attributes without one become editable rows holding no value, and NumberPool attributes are allocated from the generic's pool, which is created if it is missing. The repair is idempotent and writes nothing on healthy installs, and the upgrade fails with per-kind detail if any damage is left behind.

### Housekeeping

- Updated the base Python version of the Infrahub container image and the development environment from 3.14.3 to 3.14.7.

## [Infrahub - v1.11.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.11.0) - 2026-08-17

We're excited to announce the release of Infrahub, v1.11.0!

### Release highlights

The headline of 1.11 is **scale and performance**. Until now, almost any change caused Infrahub to redo work the change could not have affected: merging a branch re-ran every Generator and regenerated every artifact, and a single commit to a linked repository recomputed every Transformation-based computed attribute in the instance. On a large dataset that meant thousands of background tasks and an instance that stayed busy long after the merge finished. 1.11 makes that work proportional to what actually changed.

Alongside this, **webhook deliveries become first-class tasks you can inspect, retry and cancel**. A delivery used to be an anonymous step inside a larger task, so you could not see what was sent, read what came back, or resend anything without re-firing the original event.

The release centers on three themes: **performance at scale** — selective regeneration after a merge, precise Generator and computed-attribute triggers, and narrower schema validation; **operational visibility and recovery** — webhook delivery operability, and detection of and recovery from a failed merge; and **day-to-day usability** — server-side sorting and filtering, and personal date and time preferences.

### Before upgrading

#### Breaking changes

> **⚠️ Breaking changes in this release**
>
> - **Artifact workflows after target removal:** If your workflow relies on an artifact remaining available after its target is removed from the artifact definition's target group, Infrahub deletes that artifact on the next full generation pass. Capture any required content, or update the workflow, before removing the target.
> - **`infrahub git-agent`:** Scripts or automation that still call this command will no longer work after upgrading. Replace those calls with the task worker.
> - **Generated OpenAPI clients:** Code that depends on the previous component schema names in `openapi.json` needs to be updated and regenerated.
>
> The full Breaking changes section below explains the impact of each and the action to take.

#### Upgrade preparation

> **📌 Non-breaking preparation**
>
> - **Separately managed Neo4j deployments:** Upgrade Neo4j to `2026.05.0` alongside Infrahub.
> - **Python Transformations and generator definitions with external dependencies:** Add `watch` entries for modules imported from outside the Transformation's package directory.
>
> The Infrahub container image includes Python 3.14 and Neo4j 2026.05.0. Expect a one-time recomputation the first time each Transformation is imported after upgrading.

### Scale and performance

#### Work proportional to the change

##### Regenerate only what a merge actually changed

When you merge a branch or a Proposed Change, Infrahub now regenerates only the artifact and Generator definitions whose inputs the merge actually changed, and only for the members affected — instead of regenerating every definition for every member.

A merge captures its own diff and uses it to decide what to run. A definition is regenerated when its GraphQL query, its definition object, or its code changed, and its members are narrowed to the objects the change touched. Across the scenarios used to validate this, the number of regeneration tasks a merge produces fell by between 73% and 100%. When a merge runs a Generator, Infrahub waits for it to finish and then regenerates the artifacts built from the objects that Generator created or changed.

The rule the selection follows is that regenerating too much is acceptable and regenerating too little is not.

- **Fallback behavior.** A missing or unreadable diff, a definition with no fingerprint yet, and an incomplete dependency list each cause Infrahub to regenerate every member of that definition. This creates more tasks than necessary, but no affected artifact is left stale.
- **Data referenced through relationships.** An interface's description or an owner's name cannot always be resolved to specific members, so Infrahub regenerates all members of the affected definitions. Definitions that render relationship data therefore see a smaller reduction than those built directly from the changed objects.

Selective regeneration is controlled by `selective_execution_after_merge` (`INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`) and is **enabled by default**. Setting it to `false` restores full regeneration after every merge.

##### Re-run only affected Generators when a integrated repository is updated

Generators, Transformations, and GraphQL queries usually live together in a repository shared by an automation team, and any commit to the repository used to re-run every Generator across every member of its target group. Within a Proposed Change, a Generator is now re-run only when the commits in the branch affected its source file, its GraphQL query, or its definition. A typo fixed in an unrelated README no longer re-runs anything.

This extends to Generators the precise regeneration that 1.10 introduced for artifacts. Each decision to run or skip is recorded in the Proposed Change's task log, naming the file, query, or definition field responsible, so a reviewer can see why a Generator ran without tracing the repository themselves. Read-only repositories participate on the same terms, even on branches where `sync_with_git` is disabled.

Generators imported before this upgrade keep working unchanged. Infrahub applies the narrower dependency checks to a Generator definition the next time it imports that definition; until then it may re-run that Generator on any file change in the repository, so no output goes stale during the transition. Editing `.infrahub.yml` re-runs every Generator in that repository, because the file defines what each of them depends on.

For dependencies Infrahub cannot detect on its own — a helper module imported at runtime from a sibling package, for example — declare them with the optional `watch:` key on `generator_definitions` in `.infrahub.yml`:

```yaml
generator_definitions:
  - name: interface_generator
    file_path: "generators/interfaces.py"
    class_name: InterfaceGenerator
    targets: network-devices
    query: device_interfaces
    watch:
      files:
        - "generators/shared/"          # directory entries are recursive
        - "generators/helpers/naming.py"
```

##### Recompute computed attributes only when their inputs change

Two separate causes of unnecessary recomputation are addressed.

- **A commit to a linked repository** used to recompute every Transformation-based computed attribute in the instance, for every object of its kind. Infrahub now recomputes only the attributes whose Python Transformation actually changed. An edit and its exact revert leave the Transformation unchanged and trigger no work at all.
- **A schema change** used to recompute every computed attribute on the branch. A computed attribute is now recomputed only when the change affects a schema element its value depends on, including elements reached through a relationship. Where the impact cannot be determined, Infrahub falls back to recomputing every computed attribute on the branch, so nothing goes stale.

Underneath both, definitions that produce output from a repository — GraphQL queries, Transformations, artifact definitions and Generator definitions — now include a `fingerprint` attribute holding a content hash of their inputs. Because the fingerprint is branch-aware, a change to a definition is detected the same way whether it arrived by a Git import, a branch merge, a rebase or a direct edit. A null fingerprint means the definition has not been imported since upgrading.

A Python Transformation that declares no `watch` key has the commit id folded into its fingerprint, so it continues to recompute on every commit to its repository — scoped to its own attributes only, rather than to every computed attribute in the instance. Declaring `watch` with an explicit list, including an empty one, opts that Transformation into precise, commit-independent recomputation. Jinja2 Transformations no longer need the empty declaration that 1.10 required, because Infrahub resolves their dependencies from the `include`, `import`, and `extends` graph; a template dependency it cannot resolve still recomputes on every commit.

Declaring `watch` on any Transformation is now a best practice, so its outputs are regenerated only when a real dependency changes. The first import of a Transformation after upgrading computes its attributes once; that is a one-time cost, not a per-commit one.

```yaml
python_transforms:
  - name: cabling_plan
    class_name: CablingPlan
    file_path: "./transforms/cabling_plan.py"
    # cabling_plan.py imports from the src package, which Infrahub cannot detect
    # from the Transformation's own directory. Declaring it here completes the
    # dependency list, so the artifact regenerates only on a real dependency change.
    watch:
      files:
        - src/infrahub_solution_ai_dc/protocols.py
```

More information can be found in the [documentation](https://docs.infrahub.app/git-integration/infrahub-yml#declaring-extra-dependencies-with-watch).

##### Reduce recomputation work after a large merge or rebase

Merging or rebasing a branch now runs a single combined recompute pass for computed attributes, display labels and human-friendly IDs, instead of one recompute job per changed node. The work after the operation scales with the number of derived values actually affected rather than with how many nodes were touched, and the resulting values are unchanged.

Recomputed values are also now written in bulk. Previously each value took its own update task and its own API call; results are now persisted together in bounded transactions. For computed attributes backed by a Python transform, a batch initializes the transform's Git repository once for the whole batch rather than once per object, and an object whose recomputed value is unchanged is skipped entirely — so it neither writes nor triggers further recomputation. That last point removes a self-sustaining cycle in which recomputing already-correct values dispatched more recomputation.

On the reference dataset used during development, a large post-merge recomputation went from about 1,500 background tasks to two, and from about 275 seconds to about one second. Results vary with the dataset, schema, and automation definitions in each environment.

##### Validate only the constraints a change can violate

Schema constraint validation during Proposed Change checks, merges and rebases used to run against every kind in the schema, even for a branch that changed only data. It is now scoped twice over:

- to the **kinds** the change touched — plus the generics they inherit from and any kind whose uniqueness constraint reads an attribute of a changed kind;
- to the **fields** a constraint actually guards — changing an attribute that participates in no uniqueness constraint no longer re-validates that kind's uniqueness, and re-parenting a child no longer triggers the children check on the parent.

The amount of validation work no longer grows with the total size of your schema. Schema diffs between two identical branches now correctly come back empty.

#### Task and API priority

##### Task priority lanes

Background work and the operations a user is waiting on used to share a single queue, so clicking "merge" while the instance worked through a backlog meant waiting behind all of it. Infrahub now runs three priority lanes. Every task required to complete a branch create, merge, rebase, delete or validation operation is processed at the priority of that operation, and the same applies to the tasks created when a Proposed Change is merged.

- **High.** Branch create, merge, rebase, delete and validate; Proposed Change merges; Generator definition runs; schema load and check; Transformation rendering; and on-demand artifact generation.
- **Medium.** IPAM reconciliation.
- **Low.** Profile refresh, and post-merge follow-ups such as Proposed Change cancellation, automatic branch deletion, and artifact and Generator regeneration — which previously inherited the merge's own high priority.

The queues are created automatically on startup, so an upgraded instance needs no manual migration.

##### Keep the UI responsive when the instance is busy

Heavy background work and the web UI compete for the same finite API and database capacity. Because the API could not tell the two apart, a busy instance could stop serving the UI altogether and the application appeared to hang.

Requests can now declare their priority with an `X-Priority` header (`high`, `medium` or `low`; anything missing or invalid is treated as `medium`). Under sustained overload Infrahub asks lower-priority requests to retry first, returning `429 Too Many Requests` with a `Retry-After` header before the request does any work, so interactive traffic keeps flowing. The web UI sends `high` on its own calls and `low` on background traffic that can retry later.

An initial data load or a deliberate full regeneration goes through the same back-off, which protects the instance under peak load but can make that run take longer. On a normally loaded deployment no requests are rejected. Admission metrics are published on `/metrics`, and the whole layer can be switched off with `INFRAHUB_API_BACKPRESSURE_ENABLED=false`.

#### Where the performance improvements apply

These changes reduce the regeneration, recomputation, and validation created around a change. They do not make the underlying operations themselves faster.

- Changing a Transformation, artifact definition, or Generator still regenerates every artifact that depends on it.
- The time to compute and apply a merge, rebase, or diff is unchanged; the reduction is in what happens around and after those operations.
- Schema loading itself is unchanged; the reduction applies to the computed-attribute recomputation and constraint validation that follow a schema update.

### Operations and recovery

#### Webhook deliveries

When a downstream system stops acting on Infrahub events, the first question is whether the webhook fired at all. The webhook's own Tasks tab used to report no deliveries, a successful delivery recorded no payload or response, and a failure showed a Python traceback with the cause buried inside it.

Every delivery is now its own task, listed in the Tasks tab and in the webhook's related-tasks panel, recording the request URL and headers, the response status code and body, and how long the target took to respond. Large response bodies are truncated. Infrahub masks the signature, any header value sourced from the environment, and well-known credential headers such as `Authorization` and `X-API-Key`, so inspecting a delivery does not expose them.

- **Failures are readable.** An expected delivery failure — an unreachable target, a TLS problem, a timeout, an HTTP error from the receiver, a misconfiguration — is reported as a named reason with a remediation hint, such as "The target rejected the request; check the URL and authentication." Unexpected errors keep their stack trace, so a genuine defect still looks like one.
- **Deliveries retry on their own.** A failed delivery is retried up to three times, two minutes apart, rather than exhausting its retries in a few seconds as before. Every failure is retried, including a `4xx` response or a header value Infrahub cannot resolve.
- **You can retry a settled delivery.** Retrying replays the payload captured when the event fired, resolves the webhook configuration again so a corrected URL, header or signing key applies, and runs as a new delivery. The original delivery is preserved as a record.
- **You can cancel one still running.** Infrahub checks for a cancellation before each attempt, so cancelling during the wait stops the remaining ones. A request already sent cannot be recalled, and a delivery that has already settled cannot be cancelled.

#### Merge protection and recovery

If the worker running a merge is killed partway through, the instance used to be left with a half-merged default branch, a branch stuck in `MERGING`, and no way back other than restoring a backup or running manual database queries. 1.11 makes that state detectable, visible, and recoverable.

- **Writes are blocked for the duration of a merge.** Writes to both the default branch and the source branch are refused while a merge runs, and a new merge or rebase is refused until it completes. A blocked write receives a transient message asking the caller to retry shortly, and the block lifts automatically when the merge finishes or is rolled back.
- **A stalled merge is detected.** Infrahub notices when a merge's worker is no longer running, records the branch as failed, and keeps the default branch protected. Writes then receive a distinct, non-retryable error telling the operator that recovery is required — separate from the transient "merge in progress" case, so a client does not retry forever.
- **`infrahub recover merge` puts things back.** The command rolls back the partial merge on the default branch, resets the branch and any associated Proposed Change to `OPEN`, and lifts the write protection. It shows what it will do and asks for confirmation (`--yes` to skip), and it is safe to run twice — an interrupted recovery can simply be run again. Object, attribute and relationship timestamps are restored to their pre-merge values, including for objects affected by a schema migration.

The original work stays available for inspection, so once the underlying problem is resolved the same branch goes through the normal validation and review workflow again.

Branch-status rejections now also include structured GraphQL error codes — `BRANCH_ALREADY_MERGED`, `BRANCH_NEEDS_REBASE` and `MERGE_IN_PROGRESS` — so API and SDK clients can react to a code instead of matching message text.

#### Delete a repository and its related objects

Deleting a repository used to fail, because the objects it imports and generates — Transformations, checks, GraphQL queries, Generators, and the artifact definitions, artifacts, Generator instances and validators below them — are attached by mandatory relationships that Infrahub correctly refuses to break. The only way through was to delete the whole tree manually, leaf first.

Deleting a repository now removes the objects it owns along with it. Infrahub still refuses the deletion, naming the dependency, if one of those objects is required by something outside the repository, and makes no partial deletion. Validators attached to Proposed Changes, and the artifacts and Generator instances they produced, are removed too, which is the intended ownership relationship.

### Schema and data modeling

#### Write schemas against a published contract

The model that described the schema you write was a partial copy of Infrahub's internal model, and it was wrong in two directions.

Fields that only Infrahub sets — inherited, used_by, hierarchy, a derived kind — appeared in it as though you could set them. A schema that set one looked correct, loaded, and then behaved in a way the schema file did not explain.

Bounded fields were described as free-form text. As far as the published model was concerned an attribute kind was a string, with no list of the kinds that exist, so a kind that Infrahub does not have was accepted at the boundary and failed later in the load. Writing a schema meant carrying facts in your head, or in the reference
documentation, that the model should have carried itself. An AI assistant generating a schema had no list to work from at all, which is the main reason schemas generated that way needed several corrections before they loaded.

1.11 generates two contracts from the single source of truth instead: a write contract, holding exactly the fields you may set and the values each one accepts, and a read contract, which adds the fields Infrahub computes and returns. POST /api/schema/load validates every node, generic, and extension you submit against the write
contract, and reports what it will not apply.

- Read the allowed values from the contract itself. An attribute kind, a relationship kind and cardinality, and the other bounded fields are published as enums. An invalid attribute kind is reported on the attribute, because kind selects which attribute contract applies, and the message lists every kind that exists.
- Correct a bad value from the message. A constrained field set outside its allowed values, or a value out of range or of the wrong type, is rejected with the field path and the value received.
- See which of your values Infrahub ignored, instead of finding out later. A field Infrahub computes and owns is accepted, dropped, and reported as a warning naming every kind and element that carried it. Reading a schema back from GET /api/schema, editing it, and loading it again keeps working, with nothing to strip out first.
- Validate a schema file before a server sees it. `infrahubctl validate schema <file>` reports the same errors and warnings with no server involved…
- Check a schema in CI against the contract your server enforces. The write contract ships as a committed model in the Python SDK. The model is versioned with the SDK, so installing the SDK that matches your Infrahub version gives you the contract that server applies.

The same contract is what an AI assistant reads, so a generated schema can be corrected against the allowed values before it is submitted rather than after a failed load.

#### Model an IP address without a prefix length

Use the new `IPAddress` kind when the value represents an address only, such as a DNS record, an NTP or syslog target, a monitoring target, or an ACL entry. Where `IPHost` normalizes `192.0.2.1` to `192.0.2.1/32`, an `IPAddress` value keeps the address you entered,  a value that includes a prefix length or netmask is rejected. IPv6 values are stored in compressed lowercase form, and values sort lexically rather than numerically.

#### Normalize values before changing an attribute's kind

If you change an attribute to `IPHost`, `IPNetwork`, `IPAddress` or `MacAddress`, the existing values must already match the storage format the new kind requires; Infrahub now rejects the conversion when they do not. A `Text` value of `aa-bb-cc-dd-ee-ff`, for example, must be normalized before conversion to `MacAddress`, where the value is stored as `AA:BB:CC:DD:EE:FF`.

#### New ordered property on attribute schema

Attribute schemas gain an `ordered` flag. Setting it to `false` on a `List` or `JSON` attribute means reordering that attribute's elements is no longer reported as a conflict during a merge or rebase, while adding or removing an element still is.

The built-in `enum`, dropdown `choices`, `used_by` and `restricted_namespaces` attributes now use this. That resolves a case where two branches ended up holding the same set of dropdown choices in a different order and the branch could not be rebased.

### UI improvements

#### Sort and filter object and IPAM lists

Object and IPAM lists can now be sorted and filtered from the UI, using the backend ordering support added in 1.10. Sorting runs on the server, so it applies to the complete result set rather than the current page, and stays responsive on large inventories.

From a column header, sort ascending or descending, filter from the same menu, or sort by a supported attribute on a related object when the column references a single related object. From the toolbar, add multiple sort fields, reorder them to change which takes precedence, and remove the ones you no longer need. A device list can be sorted by site and then by role, or a prefix view organized by namespace while you review address capacity.

The selected sort is stored in the page URL, so the resulting view can be bookmarked or shared.

#### Set personal and organization-wide date and time preferences

Dates in the UI followed the browser's locale, and an organization had no way to set a house format. Each user can now choose their own date format and timezone from a **Preferences** card on the account Profile tab, and the choice applies wherever you sign in with the same account. Administrators holding the new `manage_global_preferences` permission set organization-wide defaults on a **Global preferences** tab. A field left unset inherits the organization default, and falls back to the browser's setting when no default exists. Personal preferences are private: reading or writing them only ever touches your own record.

#### Choose a prefix length when allocating from a pool

Allocate an IP address or prefix using the prefix length that request needs, rather than always taking the pool default. The prefix length can be set from the allocation form in the UI and inline in a GraphQL mutation. Allocating with a prefix length that conflicts with an existing reservation now returns a clear error instead of silently reusing that reservation.


#### Also in the UI

- Sort the Proposed Changes list by any sortable field; newest created appears first by default.
- A branch's details page shows whether you are working on that branch, and offers a one-click switch when you are not.
- The default branch is identified by the flag the API returns rather than by the name `main`, which reported the wrong branch when `INFRAHUB_INITIAL_DEFAULT_BRANCH` was set.
- Lists show current values immediately after records are created, edited, or deleted.
- Relationship selectors honor the schema's `common_parent` property, offering only peers that share the parent selected elsewhere in the same form.
- Hierarchical relationships show the related kind's label — **Region** or **Site** — in place of generic **Parent** and **Children** labels.
- Adding a child from a hierarchical object pre-fills the parent field.
- Markdown artifacts render Mermaid diagrams.
- The branch **Sync with Git** flag explains that it controls whether an Infrahub-created branch is propagated to Git, not whether the branch originated in Git.

### Minor changes

**Performance**

- When you request only the `id` of a cardinality-one relationship's peer, Infrahub no longer builds the full peer node.
- For very large merge and rebase diffs, Infrahub retrieves field summaries in pages bounded by `database.query_size_limit`, reducing the risk of exhausting the Neo4j heap during validation.

**Reliability**

- Merging or rebasing a branch that deletes a node refreshes the derived values of the nodes that read it across a relationship, so computed attributes, display labels and human-friendly IDs no longer reference the deleted object.
- Creating a node no longer fails when a Jinja2 computed attribute formats a value allocated from a number pool.
- Infrahub marks a Jinja2 Transformation as updated only when its content has changed.
- Repository synchronization continues when a branch that was already merged in Infrahub still exists on the remote.
- Removing a relationship from the schema closes the underlying relationship data, so stale peers do not reappear if the same identifier is added again later.
- A flow waiting for an automatic retry is given more time before it can be marked as crashed.
- TLS certificate verification failures are reported as TLS errors instead of generic connection errors.

**Telemetry**

- The daily anonymous telemetry payload adds adoption and activity signals: active accounts and account groups, open non-system branches, node counts that respect branches and time, and activity from the previous full UTC day. Each field is collected independently, and reporting remains opt-out through `INFRAHUB_TELEMETRY_OPTOUT`.

**Dependencies**

- Infrahub uses `@urql/core` instead of `@apollo/client` for frontend GraphQL requests, reducing the JavaScript bundle size without changing request behavior.
- The container image is smaller: the build toolchain is excluded from the runtime image, and `numpy` and `pyarrow` are no longer installed by default. `pyarrow` remains available through the `object-transfer` extra for `infrahubctl object load`.

### Breaking changes

Read this section before upgrading.

#### Artifact workflows after target removal

**Impact.** If your workflow relies on an artifact remaining available after its target is removed from the artifact definition's target group, Infrahub deletes that artifact on the next full generation pass instead of retaining a stale copy.

**What to do.** Capture any artifact content another workflow still needs, or update that workflow so it no longer depends on the artifact after the target is removed.

Full generation runs after a merge, after an artifact definition update, or when the generate endpoint is called with no node filter. A run limited to specific members does not delete artifacts outside that scope.

#### `infrahub git-agent`

**Impact.** Scripts, deployment automation, or operational procedures that still call `infrahub git-agent` will no longer work after upgrading, because the deprecated command has been removed.

**What to do.** Replace any remaining calls with the task worker before upgrading.

#### Generated OpenAPI clients

**Impact.** Generated clients or application code that depend on the previous component schema names in `openapi.json` need to be updated. The response body from `GET /api/schema` is unchanged.

**What to do.** Update the renamed component types and regenerate affected clients:

- `APINodeSchema` → `NodeSchemaRead`
- `APIGenericSchema` → `GenericSchemaRead`
- `APIProfileSchema` → `ProfileSchemaRead`
- `APITemplateSchema` → `TemplateSchemaRead`

### Upgrade notes

#### Runtime versions

**If:** You run Neo4j separately from the version shipped with Infrahub.

**Then:** Upgrade Neo4j to `2026.05.0` alongside Infrahub 1.11.

**Notes:** The container image includes Neo4j `2026.05.0`, up from `2025.10.1`, and Python 3.14, up from Python 3.13.

### Declare the `watch` property for Python Transformations and Generator definitions in `.infrahub.yml`

**If:** You use a Python Transformation and Generators that imports modules from outside its package directory.

**Then:** Declare those files with the `watch` key on the entry in `.infrahub.yml`. An empty `watch` list opts in.

**Notes:** Without a complete dependency declaration, Infrahub recomputes the computed attributes produced by that Transformation after every commit to its linked repository. Jinja2 Transformations no longer need the empty `watch` declaration that 1.10 required. After upgrading, the first import of each Transformation recomputes its computed attributes once.

#### Migration of an Infrahub instance

Before upgrading:

1. Delete branches that are no longer needed, so migrations are not run against unused branches.
2. Review the Breaking changes section above.
3. Upgrade existing `infrahub-sdk` installations to `v1.23.0`.
4. Back up the Infrahub instance and verify the restore procedure. See https://docs.infrahub.app/backup

Stop the existing instance:

```bash
docker compose down
```

For Docker Compose deployments, download the updated Compose file:

```bash
curl https://infrahub.opsmill.io -o docker-compose.yml
```

Set the version and start the environment:

```bash
export VERSION="1.11.0"
docker compose pull
docker compose up -d
```

For Kubernetes deployments, use the latest Helm chart supplied with this release.

Run the migrations:

```bash
docker compose exec infrahub-server infrahub upgrade
```

Restart all Infrahub services:

```bash
docker compose restart
```

### Full changelog

#### Security

- Bumped transitive docs dependencies to address Dependabot advisories: `dompurify` >= 3.4.0, `follow-redirects` >= 1.16.0, `lodash` and `lodash-es` >= 4.18.0, `postcss` >= 8.5.10, and `uuid` (v11) >= 11.1.1.

#### Removed

- Removed the `infrahub git-agent` command line utility, which was deprecated long ago and replaced by the task worker. ([#5584](https://github.com/opsmill/infrahub/issues/5584))

#### Deprecated

- Deprecated the `has_schema_changes` field on the `Branch` and `InfrahubBranch` GraphQL types. Use `schema_differs_from_default_branch` instead. `has_schema_changes` still returns the same value and is scheduled for removal in Infrahub 1.14.0.

#### Added

- Removing a relationship from a schema now closes the relationship data using that schema instead of leaving them active, but unreachable, in the graph. Previously the data was orphaned, which would resurface stale peers if a relationship with the same identifier was re-added later. ([#2474](https://github.com/opsmill/infrahub/issues/2474))
- Object Templates now expose `member_of_groups_for_instances` and `subscriber_of_groups_for_instances` relationships. Groups assigned through these fields are propagated to every object created from the template, mirroring the resource-pool pattern. The existing `member_of_groups` and `subscriber_of_groups` on a template continue to apply to the template itself only. ([#9094](https://github.com/opsmill/infrahub/issues/9094))
- Per-provider `groups_claim` setting for OAuth2 and OIDC providers: configure the JSON key used to extract the user's groups from the IdP claim payload (default `groups`). See the SSO guide for details. ([#9144](https://github.com/opsmill/infrahub/issues/9144))
- Added a Sort picker to the proposed changes list to order it by any sortable field, including creation and update dates. The list now defaults to newest created first. ([#9915](https://github.com/opsmill/infrahub/issues/9915))
- A branch's details page now says whether you're working on that branch, and lets you switch to it. When the page you're viewing isn't the branch you're working on, a notice explains that edits won't land there and offers a one-click switch.
- Added a **Global preferences** tab (`/profile/global-preferences`) to account settings, visible only to users holding the `manage_global_preferences` permission, where administrators set the organisation-wide default date format and timezone that apply to every user without a personal override.
- Added a `schema_differs_from_default_branch` field to the `Branch` and `InfrahubBranch` GraphQL types. It reports whether a branch's schema differs from the default branch, replacing the misleadingly named `has_schema_changes` field with a name that reflects what the value actually means.
- Added a `selective_execution_after_merge` setting (env `INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`) that narrows post-merge regeneration to the artifact and Generator definitions the merge actually affected, instead of regenerating every definition for every member. When enabled, a merge captures its diff and dispatches only the definitions whose query, definition, or code inputs changed, and only for the affected members. Every uncertain signal, such as a disabled flag, a missing or unreadable diff summary, a definition with no computed fingerprint, or an incomplete dependency closure, falls back to full regeneration, so no affected artifact or Generator can be left stale. On a direct merge that runs a Generator, the artifacts consuming that Generator's output are regenerated after the Generator completes. The setting is enabled by default.
- Added a database-stress signal derived from the reference permission query and used it to make API load shedding progressively tiered. The signal tracks the query's all-time fastest measured execution time (the "floor", timed over read executions of the query only) and, over a rolling window, how much slower the database currently is; new Prometheus gauges expose it (`infrahub_db_reference_query_floor_seconds`, `infrahub_db_reference_query_window_min_seconds`, `infrahub_db_reference_query_stress_ratio_median`). Database stress is now an independent shed trigger in the admission layer alongside CoDel: as a class's stress ratio climbs past its trigger, a growing fraction of that class is shed (20% within 1–2x the trigger, 50% within 2–5x, 80% at or beyond 5x) rather than the whole class at once. The triggers are tiered per class (low 5x, medium 20x, high 100x), so low-priority traffic sheds first, then medium, and high-priority (interactive) traffic is protected until the database is under extreme load. Stress-driven sheds are reported under a distinct `reason="stress"` label on `infrahub_admission_rejected_total`. New `INFRAHUB_API_BACKPRESSURE_*` settings tune the window, warm-up sample count, per-class stress thresholds, and per-class backstop caps.
- Added a new `IPAddress` attribute kind that stores a bare IP address. Unlike `IPHost`, which normalizes `192.0.2.1` to `192.0.2.1/32`, an `IPAddress` value must not carry a prefix length or netmask, and any value that does is rejected. IPv6 values are normalized to their compressed lowercase form. Note that values sort lexically rather than numerically.
- Added a personal **Preferences** card to the account Profile tab, where each user picks their own date format (from curated presets) and timezone (searchable IANA list). A field left unset inherits the organisation default, or the browser default when none is set.
- Added an `input` style variant to the Button component and adopted it for selector triggers (sort, filter, user preferences, number pool) so they match the styling of form inputs.
- Added graph path traversal feature with visual topology explorer. Users can discover paths between any two nodes, find dependencies from a source node, filter by kind and namespace, and explore the graph interactively with React Flow visualization.
- Added the `infrahub recover merge` CLI command to recover from a failed branch merge. It rolls back the partial merge on the default branch, resets the branch and any associated proposed change to `OPEN`, and lifts the write protection so the default branch is writable again. The command is operator-confirmed (skip the prompt with `--yes`) and idempotent: a run with nothing to recover reports so and makes no changes. While a branch is in the failed state, all mutations against it, including its deletion, are refused until recovery has run.
- Added the `manage_global_preferences` global permission. The `InfrahubSetPreferences` mutation enforces it when `scope` is `GLOBAL`, and the `InfrahubGlobalPreferences` query enforces it before reading the organisation-wide row (super admins implicitly pass). Writing your own preferences (`scope: USER`) or reading them (`InfrahubUserPreferences`) needs no permission — those paths only ever touch the calling account's own row.
- Added the ability to request a specific prefix length when allocating from an IP address or IP prefix pool, instead of always using the pool's default.
- Added user and global preferences as internal `StandardNode` objects (not schema nodes). A single `Preference` model holds both layers: one row per user stores that user's overrides, and a separate row stores the organisation-wide defaults (`date_format`, `timezone`). Rows are lazily created on first write; a missing row means nothing is set. The `InfrahubEffectivePreferences` GraphQL query returns the merged effective values for the calling user (user override → global default → the client's built-in default), each with the layer it was resolved from. User preferences are private by construction — there is no generic query, and the custom query and mutation only ever touch the caller's own row.
- Branch-status write rejections now carry structured GraphQL error codes in the error `extensions`: `BRANCH_ALREADY_MERGED`, `BRANCH_NEEDS_REBASE`, and `MERGE_IN_PROGRESS`. `MERGE_IN_PROGRESS` (HTTP status 423) signals a transient block while a merge is running and includes the branch being written and the branch being merged, so API and SDK clients can retry on the code instead of matching the message text.
- Infrahub can now auto-create account groups from identity-provider claims on SSO login. Opt in by configuring a claim filter under `security.auto_create_groups_filter`, with an optional per-login cap.
- Markdown artifacts now render Mermaid diagrams from ```mermaid code blocks.
- Priority-aware API backpressure. The API now accepts an optional `X-Priority` request header (`high`, `medium`, or `low`; defaults to `medium` when absent or invalid). Under sustained overload the admission layer sheds lower-priority traffic first, returning `429 Too Many Requests` with a `Retry-After` header while the request handler never runs, so interactive `high` traffic keeps flowing. Eight new `infrahub_admission_*` Prometheus metric families are exposed on `/metrics` for observability. The layer is disabled-inert on a normally-loaded deployment and can be turned off entirely with `INFRAHUB_API_BACKPRESSURE_ENABLED=false`.
- The GraphQL `order` argument now uses a single, structured interface for ordering results:

  - `order: {by: [{field: "name__value", direction: ASC}, {field: "node_metadata__created_at", direction: DESC}]}`
  - `field` is an attribute (`name__value`), a relationship attribute (`owner__name__value`), or node metadata (`node_metadata__created_at` / `node_metadata__updated_at`). It no longer carries a trailing `__asc`/`__desc` suffix.
  - `direction` is an enum (`ASC` / `DESC`) and defaults to `ASC` when omitted.
  - When provided, `by` fully replaces the schema's `order_by` default. It works at the root level, on many-relationship fields, and on hierarchical (`ancestors` / `descendants`) relationships.

  The `node_metadata` field on the `order` argument is deprecated; order by metadata through `by` using the `node_metadata__created_at` / `node_metadata__updated_at` fields instead. `node_metadata` cannot be combined with `by` in the same input.

  Schema-level `order_by` entries are unchanged and still reference object-level metadata (`node_metadata__created_at`) with an optional `__asc`/`__desc` suffix. A UUID tiebreaker is always appended so ordering is stable across paths.

  Breaking change: `node_metadata` is a reserved attribute and relationship name. Schemas that literally use `node_metadata` as an attribute or relationship name will fail to load and must rename the offending element.
- The daily anonymous telemetry payload now reports additional adoption and activity signals. New fields cover active accounts and account groups (`accounts.active`, `accounts.groups`), the count of open non-system branches (`branches.active`), and two branch- and temporal-correct node counts computed the same way the product counts nodes, distinct from the existing raw vertex total: `database.node_count.corenode` (all managed nodes) and `database.node_count.user` (user/business nodes in user-defined namespaces, excluding internal and built-in objects).

  A new `activity_24h` object summarizes what happened over the previous full UTC calendar day: logins and unique logins, validation checks started/passed/failed, artifacts created/updated, branches created/merged/deleted, and webhook deliveries that succeeded or failed.

  All changes are additive and backwards-compatible. Each field is reported independently, so a single failing source yields `null` for that field while the rest of the payload is still gathered and sent; a source that succeeds with nothing to count reports `0`. The `payload_format` identifier is advanced to reflect the new payload version.
- The frontend now declares request priority on every API call via the `X-Priority` header, sending `high` by default and `low` for opt-in background traffic. The API CORS allowed-headers list now includes `x-priority` so the header is accepted from the browser.
- Webhook deliveries are now first-class, observable tasks. Each delivery runs as its own task, retries automatically on failure, reports a classified failure reason with a remediation hint instead of a raw stack trace for expected delivery errors, records the request it sent and the response it received, and can be retried or cancelled by an operator.
- Writes to the default branch and to the source branch are now blocked for the full duration of a branch merge, and a new merge or rebase is refused while a merge is in progress. Blocked writes receive a transient message asking the caller to retry shortly, and the protection is lifted automatically once the merge completes (or is rolled back).
- `CoreGraphQLQuery`, `CoreTransformation`, `CoreArtifactDefinition`, and `CoreGeneratorDefinition` now carry an optional, branch-aware `fingerprint` attribute. It holds a content hash of the definition's inputs, laying the groundwork for change-driven regeneration. A null value means the node predates the feature or has not been re-imported since; nothing is backfilled.

#### Changed

- **Breaking:** artifact generation now deletes artifacts whose target is no longer a member of the artifact definition's target group. Previously such artifacts were left behind indefinitely as stale copies, for example after merging a branch or proposed change that removed the target from the group. Any workflow that relied on reading those leftover artifacts must capture their content before the target is removed: the next full generation pass over the definition (after a merge, a definition update, or a call to the generate endpoint without a node filter) deletes them. ([#9790](https://github.com/opsmill/infrahub/issues/9790))
- **Breaking:** GraphQL error responses now carry a stable string code in `extensions.code` (for example, `"NODE_NOT_FOUND"`, `"AUTHENTICATION_REQUIRED"`) and a typed `extensions.data` payload, plus a new integer `extensions.http_status`. Previously `extensions.code` was an integer mirroring the HTTP status. Consumers reading the integer code (most commonly on the `/graphql` auth-short-circuit path) must migrate to switching on the string code; numeric checks now read `extensions.http_status`. REST `/api/...` responses are unchanged.
- Added an explanation to the branch "Sync with Git" flag (in both the branch details view and the create-branch form) clarifying that it controls whether an Infrahub-created branch is propagated to Git, and does not indicate whether the branch originated from Git. ([#9883](https://github.com/opsmill/infrahub/issues/9883))
- Allocating from an IP address or prefix pool with a conflicting prefix length now returns a clear error instead of silently reusing the existing reservation.
- Changing an attribute's kind is now rejected when the existing values are not already stored in the canonical form of the new kind. This affects conversions into `IPHost`, `IPNetwork`, `IPAddress` and `MacAddress`. For example converting a `Text` attribute holding `aa-bb-cc-dd-ee-ff` to `MacAddress` is now refused, because the canonical form is `AA:BB:CC:DD:EE:FF`. Normalize the values first, then change the kind.
- Column headers in object lists and IPAM IP address/prefix lists now open a menu to sort the list directly from the column: sortable attribute columns offer "Sort ascending" and "Sort descending", and to-one relationship columns offer a "Sort by" entry listing the related object's sortable attributes. The header shows a direction indicator for the active sort, selecting the active direction again restores the default order, and the sort stays in sync with the toolbar Sort control and the page URL. Per-column filtering, previously opened by clicking the header, is now the "Filter" item in this menu.
- Data fetching in the web UI is being consolidated onto TanStack Query, with a shared query cache.
- Flow runs that stop sending heartbeats are marked as crashed only after a longer grace period, so a run waiting out an automatic retry is no longer prematurely marked as crashed.
- HFID attribute values are now indexed in Neo4j for faster retrieval. A migration normalizes existing HFID values to consistent all-string format and adds database indexes. The HFID lookup query has been simplified to match directly on the stored value instead of reconstructing per-field filters.
- Hierarchical `parent` and `children` relationships now display the related kind's label (for example "Region" or "Site") instead of the generic "Parent"/"Children" everywhere they appear — the object detail view, tabs, table column headers, filters, the sort picker, and create/edit forms.
- Improve merge performance by moving the logic to the database level
- Improved design of the account token list page
- Merging or rebasing a branch now runs a single coalesced recompute for computed attributes, display labels, and human-friendly ids instead of one recompute job per changed node. The work after a merge or rebase scales with the number of affected derived values rather than the changed-node count, so a large merge or rebase returns the instance to normal much faster while producing the same derived values.
- Prefect task read queries optimized to fetch only required fields. `client.all()` and `client.filters()` calls replaced with targeted `execute_graphql()` queries in `display_labels`, `hfid`, `computed_attribute`, `git`, and `generators` tasks, significantly reducing data transfer per workflow execution.
- Recomputing a Python-transform computed attribute for a batch of nodes now initializes the transform's git repository once for the whole batch instead of once per node, and persists the results in a single bulk write instead of a GraphQL mutation per node. A node whose recomputed value is unchanged is now skipped, so it neither writes nor triggers a further recompute. This shortens the trailing recompute after a merge or rebase that affects many nodes of the same kind (for example a device-type change that refreshes every device's computed description).
- Refined graph path traversal API: renamed `InfrahubDependencies` to `InfrahubReachableNodes`, renamed `node_filter` input to `kind_filter`, added generic-kind support in filters, and hardened default-branch edge filtering.
- Rewrote the CLI reference and upgrade documentation for the 1.10 upgrade/migrate UX. The `--verbose` flag on `infrahub db migrate` and `infrahub upgrade` now correctly describes that it controls internal `infrahub`/`prefect` logger output (not per-migration progress, which is always shown). Developer-facing `Raises:` blocks are no longer leaked into the rendered CLI reference. The upgrade overview now explains the six-step upgrade pipeline, what operators should expect to see during an upgrade, and how to use `db showmigrations`, `db showmigration N`, and `db migrate --plan`. Every migration now carries a required `description` field that `db showmigration N` surfaces, so operators can see what each migration does without reading the source. Migrations 068–073 ship with real descriptions; older migrations are stubbed as `N/A` for now. The migration console no longer renders Rich `file.py:NNN` debug tags on every line.
- Several built-in `Core` generic schemas that have special handling in Infrahub now restrict inheritance to the `Core` namespace via the `restricted_namespaces` field. This prevents user-defined schemas from inheriting from generics whose code paths assume a specific internal structure.

  **Breaking change.** Any user-defined node schema that inherits from one of the generics listed below must be removed (and its data deleted) before upgrading. Infrahub will refuse to load a schema that violates these restrictions and the upgrade will not complete.

  The newly restricted generics are:

  - `CoreCredential`
  - `CoreGenericAccount`
  - `CoreResourcePool`
  - `CoreIPPool`
  - `CoreTransformation`
  - `CoreBasePermission`
  - `CoreMenu`
  - `CoreComment`
  - `CoreThread`
  - `CoreValidator`
  - `CoreKeyValue`
  - `CoreTriggerRule`
  - `CoreAction`
  - `CoreNodeTriggerMatch`
- Tab navigation on detail pages (Profile, Branch details, Proposed change, Object details) now uses URL path segments (`/profile/tokens`, `/branches/foo/data`, `/proposed-changes/abc/checks`, `/objects/CoreTag/abc/members`) instead of `?tab=` query parameters. Browser back/forward navigates between tabs as distinct history entries, and each tab's content is lazy-loaded per route. Bookmarks to old `?tab=` URLs render the default tab.
- Tasks a user is blocked on now run at high priority: branch mutations (create, merge, rebase, delete, validate), proposed-change merge, and generator-definition runs dispatch at high priority when waiting for completion, as do the schema load/check, transform rendering, and on-demand artifact generation endpoints. Profile refresh tasks now run at low priority alongside the other derived-value tasks, and post-merge follow-ups (proposed-change cancellation, automatic branch deletion, artifact and Generator regeneration) run at low priority instead of inheriting high priority from the merge, with IPAM reconciliation kept at medium.
- Upgraded Python to 3.14 (from 3.13).
  Upgraded Neo4j to 2026.05.0 (from 2025.10.1).
- When a Git commit changes a Python transform, Infrahub now recomputes only the computed attributes whose transform actually changed, instead of recomputing every transform-based computed attribute on any commit. The first time a transform is imported it still recomputes its attributes once, so the initial import keeps a one-time recompute cost.
- When a proposed change includes commits to a linked repository, Infrahub now re-runs only the Generators whose source, GraphQL query, or definition was actually affected by the change, instead of running every Generator in the repository on any file change. This extends the precise regeneration already applied to artifacts. Each run or skip decision is recorded in the proposed change's task log, naming the file, query, or definition field that triggered it. Read-only repositories participate on the same terms, even on branches where `sync_with_git` is disabled. Generators imported before this change keep working unchanged and adopt the precise behavior automatically on their next import; until then they conservatively re-run on any file change in their repository.

  For dependencies Infrahub cannot detect automatically, such as helper modules imported at runtime from a sibling package, you can declare extra files with the optional `watch:` key on `generator_definitions` entries in `.infrahub.yml`. Changes to a declared file or directory then re-run that Generator's instances.
- When a proposed change includes commits to a linked repository, Infrahub now regenerates only the artifacts whose transform source, GraphQL query, or artifact definition was actually affected by the change, instead of regenerating every artifact in the repository. Each regeneration decision is recorded in the proposed change's task log, naming the file, query, or definition field that triggered it. Transformations imported before this change keep working unchanged and adopt the precise behavior automatically on their next import; until then they conservatively regenerate on any file change in their repository.

  For dependencies Infrahub cannot detect automatically, such as templates pulled in dynamically or helper modules imported at runtime, you can declare extra files with a new optional `watch:` key on `jinja2_transforms` and `python_transforms` entries in `.infrahub.yml`. Changes to a declared file or directory then trigger regeneration of that transform's artifacts.
- `POST /api/schema/load` now validates every submitted node, generic, and extension against a user-facing *write* contract, and reports the fields it does not apply instead of ignoring them.

  Constrained fields (for example an attribute `kind` or a relationship `cardinality`) set outside their allowed values, and out-of-range values, are rejected with a field-level error naming the field and the invalid value:

  ```text
  nodes[0].relationships[0].cardinality: Input should be 'one' or 'many' (received: 'several')
  ```

  Attribute `parameters` belonging to a different attribute `kind` are rejected too — for example `start_range` on a `Number` attribute, which earlier versions accepted and then discarded, so the setting silently had no effect.

  Fields Infrahub computes and owns are accepted and reported as a warning, one per distinct field, naming every kind and element that carried it. These are `inherited`, `used_by`, `hierarchy`, a relationship's `hierarchical`, a node's derived `kind` and `hash`, and the bookkeeping a schema dumped from Infrahub carries on nested blocks such as `parameters`. The submitted value is ignored, so reading a schema back from Infrahub, editing it, and loading it again keeps working:

  ```text
  'inherited' is a read-only field, the submitted value is ignored [InfraDevice.name, InfraDevice.interfaces]
  ```

  `infrahubctl schema load` and `infrahubctl schema check` print these warnings; `infrahubctl validate schema` reports them offline. A field the contract does not recognize at all — a typo, or a field removed in a newer version — is rejected as before, now with the same field-level path.

  `GET /api/schema` returns the same response body as before and still includes read-only fields such as `inherited` and `used_by`. Its OpenAPI component schemas are now named after the generated read models — `NodeSchemaRead`, `GenericSchemaRead`, `ProfileSchemaRead`, and `TemplateSchemaRead` in place of `APINodeSchema`, `APIGenericSchema`, `APIProfileSchema`, and `APITemplateSchema` — so a client generating types from `openapi.json` needs to update those type names.

  The write contract is published as a committed model in the Python SDK (`infrahub_sdk.schema.generated.write`); the SDK `validate_schema()` helper reproduces the server verdict offline, including the warnings, so a payload can be checked before submission. `client.schema.validate()` reaches the same verdict and raises `ValueError` rather than a pydantic `ValidationError`.

#### Fixed

- Removed the required asterisk from the "Sync with Git" checkbox on the create-branch form, since the checkbox is optional and the asterisk misleadingly implied it had to be checked. ([#IFC-2747](https://github.com/opsmill/infrahub/issues/IFC-2747))
- Branches containing only data changes no longer trigger every validator across every kind in the schema. Schema diffs between identical branches now come back empty, and constraint validation is scoped to the kinds with changed data or schemas. ([#2592](https://github.com/opsmill/infrahub/issues/2592))
- Fixed issue where Jinja2 Transformations were always marked as being updated during repository imports even though there were no changes. ([#3094](https://github.com/opsmill/infrahub/issues/3094))
- Added a new boolean input, allowing users to explicitly submit true, false, or null values. ([#4418](https://github.com/opsmill/infrahub/issues/4418))
- Stop `infrahub upgrade` from overwriting the status of merged or deleting branches. Branches in a terminal state (`MERGED`, `DELETING`) are now skipped, so they no longer reappear as `NEED_UPGRADE_REBASE` after an upgrade. ([#9103](https://github.com/opsmill/infrahub/issues/9103))
- Stop object-type conversion of agnostic nodes with aware attributes from re-opening merged or deleting branches. The "needs rebase" status now only applies to non-terminal branches. ([#9103](https://github.com/opsmill/infrahub/issues/9103))
- Prevent duplicated Node, Generic, Attribute, and Relationship schemas from being created in the case of a worker's in-memory schema cache being stale while updating schemas. ([#9250](https://github.com/opsmill/infrahub/issues/9250))
- Fix a bug in the merge logic that prevented the merge operation from deleting an object that had its kind or inheritance updated on the default branch after the branch being merged forked. ([#9283](https://github.com/opsmill/infrahub/issues/9283))
- Within a proposed change, Generator instances are now only re-run when the diff touches a field that the Generator's GraphQL query actually reads. Previously a Generator was dispatched for every instance sharing a relationship target with a changed node, even when the change touched no field the query depended on. ([#9378](https://github.com/opsmill/infrahub/issues/9378))
- Scope computed-attribute recompute to the schema elements a change actually touches. Previously any schema change recomputed every computed attribute on the branch (for Python-transform attributes, one recompute job per object of its kind), regardless of relevance. A computed attribute is now recomputed only when the change affects a schema element its value depends on — including elements reached through relationships — while changes whose impact cannot be determined still fall back to a full recompute so nothing goes stale. ([#9415](https://github.com/opsmill/infrahub/issues/9415))
- A Python Transformation's auto-detected dependency closure is now the file named by its `file_path` alone, rather than every Git-tracked file in the directory containing it. Keeping several Transformations in one directory - a common layout, where each sits next to its own query and helper modules - made every artifact rooted in that directory regenerate on any single-file edit there, including edits to files it never used. Helper modules a Transformation depends on are declared with the `watch.files` key in `.infrahub.yml`, where naming the containing directory covers all of them at once. Declaring `watch` with an empty `files` list on a Transformation that depends on nothing but its own file is what lets Infrahub stop treating every commit to the repository as a possible change to it. ([#9644](https://github.com/opsmill/infrahub/issues/9644))
- Added an `ordered` flag to attribute schemas. When set to `false` on a `List` or `JSON`-array attribute, reordering its elements is no longer reported as a conflict during branch merge and rebase (element counts still matter, so adding or removing an element is still a conflict). The built-in schema `enum`, dropdown `choices`, generic `used_by`, and `restricted_namespaces` attributes now use this so that two branches reordering the same list can be merged without a manual conflict resolution. ([#9764](https://github.com/opsmill/infrahub/issues/9764))
- Fixed some GraphQL requests returning an unexpected HTTP 500 error instead of a proper node-not-found (404) response. ([#9926](https://github.com/opsmill/infrahub/issues/9926))
- Fixed the proposed change Data diff tab crashing with `RangeError: Invalid array length` when the diff spans more than one page (300+ nodes). Each page also ships the ancestors of its own nodes as hierarchy context, so the same node could arrive several times; the duplicated entries corrupted the diff tree collection and crashed rendering. Each node is now kept once, preferring its changed entry when a page also delivered it as an unchanged placeholder. ([#10155](https://github.com/opsmill/infrahub/issues/10155))
- Fixed DateTime attributes on object detail pages dropping the time component of the user's preferred date format (or showing a relative phrase), while the list view rendered the full datetime. ([#10172](https://github.com/opsmill/infrahub/issues/10172))
- Fixed future dates more than a week away rendering as a relative phrase (such as "in 4 years") instead of the user's preferred date format. ([#10173](https://github.com/opsmill/infrahub/issues/10173))
- Fixed the date-format "Example" preview (and the source info tooltip) in the preferences forms rendering in the browser's timezone instead of the timezone preference being edited, which could show a time off by the zone offset or even the wrong calendar day. ([#10175](https://github.com/opsmill/infrahub/issues/10175))
- Fixed `CoreNumberPool` allocation stalling on a value that already exists on the target kind but was created outside the pool. Previously the pool kept offering such a value, the attribute's uniqueness constraint rejected it, and because the failed allocation reserved nothing the pool re-offered the same value on every subsequent attempt, parking permanently at that value. When the target attribute is unique, the pool now skips values already present on the target and advances to the next free one, so pools can be declared over ranges that already contain data. Attributes that are not unique on their own (including per-relationship uniqueness constraints) are unaffected and remain fully allocatable. ([#10179](https://github.com/opsmill/infrahub/issues/10179))
- Node and group mutation events no longer overflow the Prefect related-resources maximum after Prefect enlarges them. Events were truncated to exactly the configured maximum, and Prefect's events worker then appended its own run-context resources (flow run, task run, flow, deployment, work queue, work pool and one per flow-run tag) to the list in place, which skips the client-side validation. The enlarged event was refused by the Prefect API, which closes the event stream rather than dropping the single event. Events are now truncated to a budget that leaves room for that append. ([#10241](https://github.com/opsmill/infrahub/issues/10241))
- A TLS certificate verification failure when Infrahub connects to an external HTTPS endpoint (such as a webhook target or an SSO provider) is now reported as a TLS error instead of a generic connection error.
- Artifact and Generator regeneration during a proposed change no longer fails when a definition references a repository that has no changes in the branch diff; the missing repository is now skipped instead of aborting the task.
- Artifact generation no longer deletes artifacts that a narrowed run never examined. A run limited to specific members was treated as having evaluated the whole target group, so the stale-artifact cleanup could remove artifacts whose target was still a member. The cleanup now runs only for a pass that examined every member.
- Fix the "Resource Pool" tab on the IP prefix detail view so that it now lists both `CoreIPPrefixPool` and `CoreIPAddressPool` pools that have the prefix as a resource. A new `CoreIPPool` generic groups the two pool types and the `BuiltinIPPrefix.resource_pool` relationship now points at it. A database migration retroactively consolidates the IP pool ↔ IP prefix relationships.

  **Breaking change for GraphQL clients.** Because `BuiltinIPPrefix.resource_pool` now returns the abstract `CoreIPPool` generic (instead of the concrete `CoreIPAddressPool`), any existing GraphQL queries that selected fields directly under `resource_pool` will need to be updated to use inline fragments for fields that are specific to `CoreIPAddressPool` or `CoreIPPrefixPool`. For example:

  ```graphql
  # Before
  query {
    BuiltinIPPrefix {
      edges { node { resource_pool { edges { node { name { value } default_address_type { value } } } } } }
    }
  }

  # After
  query {
    BuiltinIPPrefix {
      edges { node { resource_pool { edges { node {
        name { value }
        ... on CoreIPAddressPool { default_address_type { value } }
        ... on CoreIPPrefixPool  { default_prefix_type  { value } }
      } } } } }
    }
  }
  ```

  Fields that exist on the `CoreResourcePool` generic (`name`, `description`) can still be selected directly without a fragment.
- Fixed Python transform based computed attributes not being configured after a repository commit update. The trigger template referenced `event.payload['commit']` instead of `event.payload['data']['commit']`; starting with Prefect 3.7 an undefined template reference fails the whole automation action instead of rendering an empty string, so the setup workflow never ran.
- Fixed display labels and human-friendly ids that read across a relationship not refreshing when they were recomputed by their own id. Resolving a cross-node template overwrote the cached own-id filter in place, so a later self recompute queried with the relationship filter, matched no node, and left the stored value stale.
- Fixed the focus ring on text inputs being clipped on the left and right edges when an object form is opened inside a sheet (for example the "Add object" form). The form no longer adds its own redundant scroll container, so the ring is drawn in full.
- Merging or rebasing a branch that deletes a node now refreshes the derived values of the nodes that read the deleted node across a relationship. Their computed attributes, display labels, and human-friendly ids no longer keep naming the deleted node.
- Proposed change action buttons (approve, reject, merge, close, draft) now surface the actual backend error message in the toast instead of a generic "An error occurred" message, making failures easier to diagnose.
- Python computed attributes no longer recompute on updates to nodes their query never reads. When a query followed a relationship whose peer is a generic, a trigger was created for every member kind of that generic, including kinds no field was read from. Those triggers carried no field filter, so any update to such a node started a recompute, and the values that recompute wrote could match the same triggers again and cascade.
- Python computed attributes now recompute when a `hfid` they read changes, and no longer recompute on every update to a kind whose `display_label` they read. A query that only read the `hfid` of a node got no trigger at all, because the query analyzer did not record `hfid` as a field. A query that read a `display_label` got a trigger with no field filter, so any update to that kind started a recompute. Both node properties are now reported under the name the schema and the change events use, so the trigger filters on them directly.
- Recovering from a failed branch merge now restores `updated_at`/`updated_by` metadata for objects, attributes, and relationships affected by a schema migration, such as changing the inheritance of a schema or adding a new attribute.
- Rolling back a failed branch merge now fully restores `updated_at`/`updated_by` metadata. Objects that first landed on the default branch as part of the failed merge have their merge-time stamps cleared instead of keeping the failed merge timestamp, and a recovery that is interrupted partway through can be re-run without leaving merge-time metadata or orphaned graph records behind.
- Schema and graph migrations now retry transient database errors (such as deadlocks) on a fresh transaction instead of failing the migration, matching the retry behavior already applied to mutations and resolvers.
- Schema constraint validation triggered by a data change now runs only the node-level constraints (uniqueness and hierarchy) whose specific field or path was actually modified, instead of every node-level constraint defined on the changed kind. A change to an attribute that participates in no uniqueness constraint no longer re-validates the kind's uniqueness, reducing the work performed during proposed-change checks, merges, and rebase operations.
- Selective regeneration after a merge now narrows Generator instances to the members actually impacted, instead of rerunning every instance in the group.
- Selective regeneration no longer skips an artifact or Generator when the change lands on a node the definition's query reads through a relationship. Such a node is not tracked as a member of the query's target group, so narrowing previously resolved it to no subscriber at all and left the output stale; these changes now regenerate every member of the definition instead. This also covers a kind the query reads both directly and through a relationship, which was mistaken for a directly-targeted kind.
- The SSO default group (`sso_user_default_group`) is now only assigned on a user's first login, when their external identity is created. Previously it was re-applied on every login whenever the identity provider returned no group claims, so an administrator who removed a user from the default group would find them added back on their next login. Groups derived from identity-provider claims continue to be synchronized on every login.
- Webhook task runs are now discoverable from the webhook related tasks panel.
- When adding a child to a hierarchical object (for example a Country under a Continent), the creation form now pre-fills the parent field with that object, so the parent no longer has to be selected by hand.
- `POST /api/schema/load` now returns the warnings it collected even when the submitted schema matches the one already loaded. Previously the response for an unchanged schema omitted them, so a deprecation or read-only-field warning went unreported on every load after the first.

#### Housekeeping

- Upgraded FastAPI to `0.141.1` and the OpenTelemetry instrumentation and exporter stack to the `0.65b0`/`1.44.0` line. This unblocks native FastAPI frontend serving and picks up the OpenTelemetry instrumentation fix required for FastAPI 0.137 and later. ([#10101](https://github.com/opsmill/infrahub/issues/10101))
- Introduced a shared `isRelationshipSchema` type guard in the frontend schema entity and routed the previously inline `"peer" in fieldSchema` field-schema checks through it, so attribute/relationship discrimination now lives in one tested place instead of being duplicated across form, table, filter and detail components.
- Made the Neo4j Bolt connector thread-pool ceiling tunable in the testcontainers stacks via the `INFRAHUB_TESTING_DB_BOLT_THREAD_POOL_MAX_SIZE` environment variable (defaulting to Neo4j's own `400`, so normal test runs are unaffected). Heavy dataset/performance runs can raise it to avoid `Neo.TransientError.Request.NoThreadsAvailable` when a wide computed-attribute recompute fan-out saturates the pool.
- Refactored permission system to extract decision logic into a single `PermissionResolver` class. `PermissionManager` now delegates resolution to the resolver and the permission report uses the same resolver, ensuring the GraphQL pipeline and UI report always agree.
- Replaced the frontend GraphQL transport (`@apollo/client`) with the lighter `@urql/core`, reducing the JavaScript bundle size. Apollo was used transport-only (no hooks, no cache); all request behavior — auth, request priority, error routing, token refresh, and file uploads — is preserved. No user-facing behavior changes.
- Restructured the frontend tooling around a pnpm workspace:

  - All frontend packages (`app`, `packages/ui`, and the `schema-visualizer` git submodule) are now members of a single pnpm workspace at `frontend/` with one shared lock file; local edits to packages are live-symlinked into the app without re-installing.
  - Cross-package dependency versions are managed through the pnpm `catalog:`, giving a single source of truth for shared dependencies.
  - Hardened the pnpm configuration: install-time build scripts are disallowed (`allowBuilds`), and Playwright versions are pinned via `overrides`.
  - Restructured the node stages of `development/Dockerfile` (shared node base, frontend, docs) with BuildKit cache mounts, enabling parallel builds and much better layer-cache reuse; `pnpm install` only re-runs when a manifest changes.
- Significantly reduced the size of the Infrahub container image: the build toolchain now lives in a dedicated build stage that is excluded from the runtime image, and the `numpy` and `pyarrow` dependencies are no longer installed by default (`pyarrow` remains available via the `object-transfer` extra for `infrahubctl object load`).

## [Infrahub - v1.10.9](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.9) - 2026-08-19

### Fixed

- Fixed a crash when loading the Tasks page where a task was tagged with a related node whose kind could no longer be resolved (for example a deleted definition or a stale tag). Such unresolvable related nodes are now omitted from the task instead of causing a GraphQL resolver error. ([#9662](https://github.com/opsmill/infrahub/issues/9662))
- Renaming an attribute in a schema on a branch now correctly closes the old attribute instead of only opening a newer path to the new attribute. This issue would have been mostly invisible to the user unless an attribute was renamed on a user's branch and that branch was then rebased, in which case there could be duplicated paths to the new attribute which could result in unexpected behavior when updating its value.

## [Infrahub - v1.10.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.8) - 2026-08-14

### Fixed

- Fixed the proposed change Data diff tab crashing with `RangeError: Invalid array length` when the diff spans more than one page (300+ nodes). Each page also ships the ancestors of its own nodes as hierarchy context, so the same node could arrive several times; the duplicated entries corrupted the diff tree collection and crashed rendering. Each node is now kept once, preferring its changed entry when a page also delivered it as an unchanged placeholder. ([#10155](https://github.com/opsmill/infrahub/issues/10155))
- Fixed `CoreNumberPool` allocation stalling on a value that already exists on the target kind but was created outside the pool. Previously the pool kept offering such a value, the attribute's uniqueness constraint rejected it, and because the failed allocation reserved nothing the pool re-offered the same value on every subsequent attempt, parking permanently at that value. When the target attribute is unique, the pool now skips values already present on the target and advances to the next free one, so pools can be declared over ranges that already contain data. Attributes that are not unique on their own (including per-relationship uniqueness constraints) are unaffected and remain fully allocatable. ([#10179](https://github.com/opsmill/infrahub/issues/10179))
- Node and group mutation events no longer overflow the Prefect related-resources maximum after Prefect enlarges them. Events were truncated to exactly the configured maximum, and Prefect's events worker then appended its own run-context resources (flow run, task run, flow, deployment, work queue, work pool and one per flow-run tag) to the list in place, which skips the client-side validation. The enlarged event was refused by the Prefect API, which closes the event stream rather than dropping the single event. Events are now truncated to a budget that leaves room for that append. ([#10241](https://github.com/opsmill/infrahub/issues/10241))
- Schema and graph migrations now retry transient database errors (such as deadlocks) on a fresh transaction instead of failing the migration, matching the retry behavior already applied to mutations and resolvers.

## [Infrahub - v1.10.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.7) - 2026-08-11

### Changed

- Improved the performance of GraphQL queries that only request the `id` of a cardinality-one relationship's peer. When no properties, metadata, or additional node fields are requested, the resolver now returns the peer ID already loaded on the parent instead of hydrating a full peer node, reducing database work on relationship-heavy queries.

### Fixed

- Fixed artifact generation storing the text None when a transform returned no data, it now fails with an error naming the transform instead. ([#5303](https://github.com/opsmill/infrahub/issues/5303))
- Fixed node creation failing when a Jinja2 computed attribute formatted a value sourced from a number pool; the computed attribute now renders once the pool value has been allocated. ([#7836](https://github.com/opsmill/infrahub/issues/7836))
- Fixed artifact generation failing for repositories whose default branch is not named main. ([#8749](https://github.com/opsmill/infrahub/issues/8749))
- Merging an Infrahub branch now reliably writes the merge back to a repository's non-`main` default branch on the remote, regardless of which task worker executes the merge. ([#9568](https://github.com/opsmill/infrahub/issues/9568))
- Fixed the object creation form auto-selecting the first available object in the parent filter of a relationship to a hierarchical node (e.g. the **Device** filter when adding an interface's lag). The parent filter now starts empty and is only pre-filled from an existing relationship value or parent context. ([#9634](https://github.com/opsmill/infrahub/issues/9634))
- Fixed deleting a large branch failing with a database out-of-memory error and leaving the branch and its data behind. Branches left behind by an earlier failure are now cleaned up on upgrade. ([#9889](https://github.com/opsmill/infrahub/issues/9889))
- Fixed git repository synchronization halting when a branch that had been merged still existed on the remote. ([#9931](https://github.com/opsmill/infrahub/issues/9931))
- Fixed group mutation events (`member_added` / `member_removed`) being silently dropped when a single mutation changed a few hundred members or more. The event's related resources are now consolidated to one entry per member and per ancestor and capped at the Prefect maximum, so the event is always recorded and membership-driven automations keep firing regardless of how many members change at once. The full member list remains available in the event payload. ([#10127](https://github.com/opsmill/infrahub/issues/10127))
- Fixed the ordering of repository tests in a proposed change. Smoke tests now run before unit tests, and unit tests before integration tests, instead of being ordered by resource kind only. ([#10170](https://github.com/opsmill/infrahub/issues/10170))
- Fixed branches imported from a Git repository being created without the sync with Git flag, which caused merges to skip the Git side. ([#10208](https://github.com/opsmill/infrahub/issues/10208))
- Fixed relationship selectors in object forms not honoring the `common_parent` schema property. The options are now filtered to peers that share the same parent as the value picked for the referenced relationship in the same form, instead of listing every peer. Changing that parent clears a now-invalid selection, and the inline "Add new" form pre-fills the parent when one is already selected so a created peer stays valid.
- Fixed the Git repositories homepage widget linking to the generic `CoreGenericRepository` kind: repositories now open on their own kind, so the details page and edit form show all of their fields.
- Fixed the object edit form failing with a GraphQL `profiles` error when an object is opened through a kind whose GraphQL type has no `profiles` field, such as `CoreGenericRepository`. The form now requests `profiles` only for kinds that expose it.
- Fixed the task status button in the header sending you to the tasks page on the default branch instead of the branch you were working on.
- Fixed schema migrations during a branch rebase using the destination branch's current schema as their baseline instead of the schema the branch was created from. Any schema element that was added on the destination branch after the branch forked already looked pre-existing to the migrations, so the work needed to bring branch data in line was skipped. Migrations now run against the branch-creation schema, which still reflects what changed on either side.
- Fixed a branch rebase that fails while running its migrations restoring the wrong schema for the branch. The branch was left with the schema it was created from, silently dropping any schema change made on the branch itself, and the recorded schema hash was wrong as a result. The rollback now restores the schema the branch had immediately before the rebase started.

## [Infrahub - v1.10.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.6) - 2026-07-28

### Changed

- Node creation no longer issues a redundant database query to resolve peers for empty many-cardinality relationships, since a newly created node has none stored yet. This removes hundreds of round-trips during the first-time database initialization and speeds up node creation.

### Fixed

- Deleting a repository now cascades to the objects it manages (transforms, checks, GraphQL queries, generators, and their artifact definitions, artifacts, and validators), so a repository can be removed in a single operation instead of deleting each dependent object by hand. ([#3076](https://github.com/opsmill/infrahub/issues/3076))
- Following an IP prefix or address link from the relationship tabs of an IPAM namespace now keeps you in that namespace, instead of redirecting to the default namespace. ([#9892](https://github.com/opsmill/infrahub/issues/9892))
- Fixed git-sync repository import getting stuck on the previous commit when a check definition removed from the repository was still referenced by a proposed change. ([#9934](https://github.com/opsmill/infrahub/issues/9934))
- Fixed the branch and proposed change diff view not showing changed objects in the tree when their parent object had no changes of its own. ([#10010](https://github.com/opsmill/infrahub/issues/10010))
- Fixed the object creation form when adding a component from its parent's tab (e.g. adding an interface from a device): the parent is now pre-selected and the create form opens directly, even when the component's parent relationship points to a generic rather than a concrete node.
- The proposed changes list is now ordered by creation date with the newest first, on both the open and closed tabs.
- Fixed schema updates that remove a node with an object template leaving the branch schema permanently out of sync across workers ([#10049](https://github.com/opsmill/infrahub/issues/10049))
- Branch rebase and merge no longer validate schema constraints for attributes and relationships that were not actually modified on the branch. The query collecting the changed fields of a diff could match nodes belonging to other branches' diffs and to already-merged diffs, which would inflate the set of constraints to check.

## [Infrahub - v1.10.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.5) - 2026-07-15

### Fixed

- Fix a race condition for recalculating a diff following a rebase. After a branch is rebased, an asynchronous job is queued to recalculate the diff for that branch. If a user tried to update the diff for that branch or merge the branch before the recalculation completed then they would receive an error like `ResourceNotFoundError: Multiple diffs for branch ... with tracking_id ...`. The diff update logic is now updated to handle post-rebase recalculation correctly if it is reached before the recalculation job. ([#9898](https://github.com/opsmill/infrahub/issues/9898))
- Removing a node from the schema on a branch and merging that branch no longer fails with a `SchemaNotFoundError`. Schema elements without a persisted id (such as the virtual `profiles` relationship) are now compared by value instead of being reported as spurious additions in the schema diff. ([#9899](https://github.com/opsmill/infrahub/issues/9899))
- Fresh installations now persist the deprecated-model markers, so the core-schema diff computed by `infrahub upgrade` starts out empty instead of always reporting `LineageSource` and `LineageOwner` as changed on an up-to-date installation.
- Merging a rebased branch now computes schema migrations against the rebase point, so schema changes the rebase already incorporated from the destination branch are no longer counted a second time.
- Schema errors raised during background operations (such as `SchemaNotFoundError`) now surface the actual error instead of an unrelated serialization `TypeError`.

## [Infrahub - v1.10.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.4) - 2026-07-13

### Added

- `INFRAHUB_DB_ADDRESS` now accepts a comma-separated list of cluster members.

### Fixed

- The `INFRAHUB_DB_DATABASE` name validation now matches Neo4j's naming rules: names may contain dashes, must be 3-63 characters long, and may no longer end with a dot. Database names that contain dashes or dots are now correctly quoted when the database is created, so they no longer fail with a Cypher syntax error.
- Changing a Git repository's location now re-points the server-side clone and fetches from the new remote, instead of staying stuck on the previous commit. ([#9811](https://github.com/opsmill/infrahub/issues/9811))
- The `configure-action-rules` background flow no longer crashes when a trigger rule references a group or Generator that does not resolve on the branch being read (a required relationship left dangling by a deleted, orphaned, or branch-missing peer). The offending rule is now skipped with a warning that names it, and the remaining trigger rules are reconciled normally instead of the whole flow aborting. ([#9829](https://github.com/opsmill/infrahub/issues/9829))
- Outbound webhook payloads now include the `account_id` of the account that triggered the event again, instead of always sending `null`. ([#9881](https://github.com/opsmill/infrahub/issues/9881))
- Changing the `identifier` of a relationship in a schema is now rejected with a "not supported" validation error instead of being silently incorrectly applied.
- Deleting a node with cascade now checks mandatory relationships across the full set of cascaded objects. Previously a node pulled into the delete by a cascade could be removed even while a mandatory relationship from an object outside the delete set still referenced it, leaving a dangling mandatory relationship. Such deletes are now correctly blocked with a validation error.
- Fixed a bug where some human-friendly ID (HFID) values were stored with non-string elements (such as numbers) instead of all strings. Fresh upgrades now normalize all values, and instances that already upgraded are repaired automatically on their next upgrade.

## [Infrahub - v1.10.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.3) - 2026-07-07

### Added

- Global initialization locks now expire automatically after a configurable time-to-live (20 minutes by default, set via `INFRAHUB_CACHE_INIT_LOCK_TTL_MINS`). Previously, if a worker died while holding the task-manager or registry initialization lock, the lock was never released and Infrahub could not start until the key was manually deleted from Redis. The lock now auto-expires so the platform recovers on its own. This applies to the Redis cache driver. ([#9277](https://github.com/opsmill/infrahub/issues/9277))

### Fixed

- The search bar now finds an IPv6 address or prefix entered with a prefix length regardless of how it is written. Previously, typing an IPv6 value with host bits set (for example `2a0b:2081:1:d3::1/127`), or its non-collapsed extended form, returned no matching object even when one existed, because the value was not normalized before the lookup. ([#9788](https://github.com/opsmill/infrahub/issues/9788))
- Running **Check connectivity** on a repository now records the outcome in the repository's operational status. Previously a failed check (for example an unreachable Git server returning an HTTP 504) was only shown to the caller, so the repository kept displaying **Online** and **In sync** while it was actually unreachable. A failed check now sets the status to **Connectivity Error**, **Credential Error**, or **Error**, and a successful check sets it back to **Online**. HTTP 5xx gateway errors and connection timeouts are now classified as connection errors. ([#9818](https://github.com/opsmill/infrahub/issues/9818))
- Filtering tasks by an id that is not a valid UUID now returns a validation error instead of an internal server error.
- Fix diff calculation to correctly handle the case when a relationship was removed from a branch's schema while the other branch changed a non-peer property (source, owner, or protected flag) of that relationship. This issue would have previously appeared as a `DiffNoPeerIdError`.
- Fixed exhaustive path traversal (`shortest_paths_only: false`) so it no longer tries to search through graphs that are too dense. When the paths through a node fan out too far to enumerate within budget, the search now stops and reports how deep it got via `truncated_at_depth`, instead of building an unbounded set of paths in memory. It also no longer returns spurious or duplicate paths through a node that has been renamed or re-parented by a schema migration.
- Fixed the branch merge rollback so that a database error (such as an out-of-memory error) raised partway through the bulk merge queries no longer leaves partially merged data on the destination branch. The rollback now removes every change stamped with the merge timestamp even when the failure occurred before the merge finished discovering the affected nodes.
- The task GraphQL query now returns the correct log count when only `logs { count }` is selected, without requesting the log entries themselves.

## [Infrahub - v1.10.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.2) - 2026-07-03

### Fixed

- Node mutation events are no longer silently dropped when the node has a large number of relationship peers. Previously, creating or updating a node with roughly 250 or more peers (for example a trunk interface tagging a large VLAN range) produced an event whose related resources exceeded the maximum accepted by the task manager, which rejected the whole event: it never appeared in the node's activity log and automation triggers never fired for it. The related resources are now capped at that maximum, keeping the node-scoped entries and as many relationship updates as fit. ([#9794](https://github.com/opsmill/infrahub/issues/9794))
- Display labels, human-friendly IDs, and computed attributes that read across a relationship no longer error when the related peer is missing, such as after the peer has been deleted. The missing value now resolves as empty. This previously caused branch merge, rebase, and diff calculation to fail.

## [Infrahub - v1.10.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.1) - 2026-06-30

### Added

- Add "shortest paths only" toggle to a path traversal request so that user can select the faster, shortest paths only query or the exhaustive version. Add "truncated at depth" to the path traversal response to indicate at which depth a request timed out. Update the frontend to support the new toggle and display a warning message if the response is truncated.

### Fixed

- Periodic Git synchronization now imports new commits on a repository's configured default branch when that branch is not `main`. Previously the sync loaded repositories without their `default_branch` attribute, fell back to the schema default of `main`, and failed to locate the worktree, leaving such repositories pinned to a stale commit while still reporting `in-sync`. ([#9600](https://github.com/opsmill/infrahub/issues/9600))
- Fixed branches with a slash in their name (e.g. feature/my-branch) not being clickable on the Branches page. ([#9716](https://github.com/opsmill/infrahub/issues/9716))
- Restored webhook delivery: configured webhooks now fire for every triggering event, including events not associated with a branch such as account activity, instead of silently sending no request. ([#9742](https://github.com/opsmill/infrahub/issues/9742))
- Fixed webhook automation configuration running a database read on the shared worker database without opening its own session. This left a Neo4j session cached on the shared connection and could trigger `RuntimeError: read() called while another coroutine is already waiting for incoming data` in concurrently running flows. Webhook configuration now opens a dedicated read-only session.
- Merging a branch that changes a computed attribute, display label, or human-friendly ID template now refreshes those derived values on nodes that exist only on the target branch. Previously the merge applied the new schema without emitting a schema-update event, so the backfill never ran and the affected nodes kept stale values.
- Merging two branches that each introduced the same unique value could leave duplicate values on the destination branch. A proposed change validated its schema and data integrity earlier in its pipeline but the merge relied on those point-in-time results, so a violation introduced by another branch merged in the meantime was missed. Constraint validation now runs as part of the merge itself, so both proposed-change merges and direct branch merges are checked against the current state of the destination branch. The schema-integrity check also now validates relationship constraints, which were previously skipped. ([#9704](https://github.com/opsmill/infrahub/issues/9704))

### Housekeeping

- Action parameters for all event-driven automations — computed attributes, profiles, human-friendly IDs, display labels, action rules, and schema and branch triggers — are now rendered through a shared helper as explicit string templates, hardening them against the same parameter-serialization failure addressed for webhooks. ([#9742](https://github.com/opsmill/infrahub/issues/9742))

## [Infrahub - v1.10.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.10.0) - 2026-06-24

### Security

- Bumped transitive docs dependencies to address Dependabot advisories: `dompurify` >= 3.4.0, `follow-redirects` >= 1.16.0, `lodash` and `lodash-es` >= 4.18.0, `postcss` >= 8.5.10, and `uuid` (v11) >= 11.1.1.

### Added

- Object Templates now expose `member_of_groups_for_instances` and `subscriber_of_groups_for_instances` relationships. Groups assigned through these fields are propagated to every object created from the template, mirroring the resource-pool pattern. The existing `member_of_groups` and `subscriber_of_groups` on a template continue to apply to the template itself only. ([#9094](https://github.com/opsmill/infrahub/issues/9094))
- Per-provider `groups_claim` setting for OAuth2 and OIDC providers: configure the JSON key used to extract the user's groups from the IdP claim payload (default `groups`). See the SSO guide for details. ([#9144](https://github.com/opsmill/infrahub/issues/9144))
- Added graph path traversal feature with visual topology explorer. Users can discover paths between any two nodes, find dependencies from a source node, filter by kind and namespace, and explore the graph interactively with React Flow visualization.
- Infrahub can now auto-create account groups from identity-provider claims on SSO login. Opt in by configuring a claim filter under `security.auto_create_groups_filter`, with an optional per-login cap.
- The GraphQL `order` argument now uses a single, structured interface for ordering results:

  - `order: {by: [{field: "name__value", direction: ASC}, {field: "node_metadata__created_at", direction: DESC}]}`
  - `field` is an attribute (`name__value`), a relationship attribute (`owner__name__value`), or node metadata (`node_metadata__created_at` / `node_metadata__updated_at`). It no longer carries a trailing `__asc`/`__desc` suffix.
  - `direction` is an enum (`ASC` / `DESC`) and defaults to `ASC` when omitted.
  - When provided, `by` fully replaces the schema's `order_by` default. It works at the root level, on many-relationship fields, and on hierarchical (`ancestors` / `descendants`) relationships.

  The `node_metadata` field on the `order` argument is deprecated; order by metadata through `by` using the `node_metadata__created_at` / `node_metadata__updated_at` fields instead. `node_metadata` cannot be combined with `by` in the same input.

  Schema-level `order_by` entries are unchanged and still reference object-level metadata (`node_metadata__created_at`) with an optional `__asc`/`__desc` suffix. A UUID tiebreaker is always appended so ordering is stable across paths.

  Breaking change: `node_metadata` is a reserved attribute and relationship name. Schemas that literally use `node_metadata` as an attribute or relationship name will fail to load and must rename the offending element.

### Changed

- **Breaking:** GraphQL error responses now carry a stable string code in `extensions.code` (e.g. `"NODE_NOT_FOUND"`, `"AUTHENTICATION_REQUIRED"`) and a typed `extensions.data` payload, plus a new integer `extensions.http_status`. Previously `extensions.code` was an integer mirroring the HTTP status. Consumers reading the integer code (most commonly on the `/graphql` auth-short-circuit path) must migrate to switching on the string code; numeric checks now read `extensions.http_status`. REST `/api/...` responses are unchanged.
- HFID attribute values are now indexed in Neo4j for faster lookups. A migration normalizes existing HFID values to consistent all-string format and adds database indexes. The HFID lookup query has been simplified to match directly on the stored value instead of reconstructing per-field filters.
- Improve merge performance by moving the logic to the database level
- Improved design of the account token list page
- Prefect task read queries optimized to fetch only required fields. `client.all()` and `client.filters()` calls replaced with targeted `execute_graphql()` queries in `display_labels`, `hfid`, `computed_attribute`, `git`, and `generators` tasks, significantly reducing data transfer per workflow execution.
- Refined graph path traversal API: renamed `InfrahubDependencies` to `InfrahubReachableNodes`, renamed `node_filter` input to `kind_filter`, added generic-kind support in filters, and hardened default-branch edge filtering.
- Rewrote the CLI reference and upgrade documentation for the 1.10 upgrade/migrate UX. The `--verbose` flag on `infrahub db migrate` and `infrahub upgrade` now correctly describes that it controls internal `infrahub`/`prefect` logger output (not per-migration progress, which is always shown). Developer-facing `Raises:` blocks are no longer leaked into the rendered CLI reference. The upgrade overview now explains the six-step upgrade pipeline, what operators should expect to see during an upgrade, and how to use `db showmigrations`, `db showmigration N`, and `db migrate --plan`. Every migration now carries a required `description` field that `db showmigration N` surfaces, so operators can see what each migration does without reading the source. Migrations 068–073 ship with real descriptions; older migrations are stubbed as `N/A` for now. The migration console no longer renders Rich `file.py:NNN` debug tags on every line.
- Several built-in `Core` generic schemas that have special handling in Infrahub now restrict inheritance to the `Core` namespace via the `restricted_namespaces` field. This prevents user-defined schemas from inheriting from generics whose code paths assume a specific internal structure.

  **Breaking change.** Any user-defined node schema that inherits from one of the generics listed below must be removed (and its data deleted) before upgrading. Infrahub will refuse to load a schema that violates these restrictions and the upgrade will not complete.

  The newly restricted generics are:

  - `CoreCredential`
  - `CoreGenericAccount`
  - `CoreResourcePool`
  - `CoreIPPool`
  - `CoreTransformation`
  - `CoreBasePermission`
  - `CoreMenu`
  - `CoreComment`
  - `CoreThread`
  - `CoreValidator`
  - `CoreKeyValue`
  - `CoreTriggerRule`
  - `CoreAction`
  - `CoreNodeTriggerMatch`
- Tab navigation on detail pages (Profile, Branch details, Proposed change, Object details) now uses URL path segments (`/profile/tokens`, `/branches/foo/data`, `/proposed-changes/abc/checks`, `/objects/CoreTag/abc/members`) instead of `?tab=` query parameters. Browser back/forward navigates between tabs as distinct history entries, and each tab's content is lazy-loaded per route. Bookmarks to old `?tab=` URLs render the default tab.
- The web UI's data-fetching layer has been unified on TanStack Query. Previously the frontend mixed two libraries (Apollo and TanStack) for talking to the GraphQL API, with caching disabled globally. Lists, detail pages and forms now share a single caching layer, so navigating back to a page you just visited reuses the data instead of refetching it, and the JavaScript bundle is smaller. No user action is required and there are no URL changes from this update.
- When a proposed change includes commits to a linked repository, Infrahub now regenerates only the artifacts whose transform source, GraphQL query, or artifact definition was actually affected by the change, instead of regenerating every artifact in the repository. Each regeneration decision is recorded in the proposed change's task log, naming the file, query, or definition field that triggered it. Transforms imported before this change keep working unchanged and adopt the precise behavior automatically on their next import; until then they conservatively regenerate on any file change in their repository.

  For dependencies Infrahub cannot detect automatically, such as templates pulled in dynamically or helper modules imported at runtime, you can declare extra files with a new optional `watch:` key on `jinja2_transforms` and `python_transforms` entries in `.infrahub.yml`. Changes to a declared file or directory then trigger regeneration of that transform's artifacts.

### Fixed

- Removed the required asterisk from the "Sync with Git" checkbox on the create-branch form, since the checkbox is optional and the asterisk misleadingly implied it had to be checked. ([#IFC-2747](https://github.com/opsmill/infrahub/issues/IFC-2747))
- Added a new boolean input, allowing users to explicitly submit true, false, or null values. ([#4418](https://github.com/opsmill/infrahub/issues/4418))
- Stop `infrahub upgrade` from overwriting the status of merged or deleting branches. Branches in a terminal state (`MERGED`, `DELETING`) are now skipped, so they no longer reappear as `NEED_UPGRADE_REBASE` after an upgrade. ([#9103](https://github.com/opsmill/infrahub/issues/9103))
- Stop object-type conversion of agnostic nodes with aware attributes from re-opening merged or deleting branches. The "needs rebase" status now only applies to non-terminal branches. ([#9103](https://github.com/opsmill/infrahub/issues/9103))
- Prevent duplicated Node, Generic, Attribute, and Relationship schemas from being created in the case of a worker's in-memory schema cache being stale while updating schemas. ([#9250](https://github.com/opsmill/infrahub/issues/9250))
- Fix a bug in the merge logic that prevented the merge operation from deleting an object that had its kind or inheritance updated on the default branch after the branch being merged forked. ([#9283](https://github.com/opsmill/infrahub/issues/9283))
- Within a proposed change, generator instances are now only re-run when the diff touches a field that the generator's GraphQL query actually reads. Previously a generator was dispatched for every instance sharing a relationship target with a changed node, even when the change touched no field the query depended on. ([#9378](https://github.com/opsmill/infrahub/issues/9378))
- Fix the "Resource Pool" tab on the IP prefix detail view so that it now lists both `CoreIPPrefixPool` and `CoreIPAddressPool` pools that have the prefix as a resource. A new `CoreIPPool` generic groups the two pool types and the `BuiltinIPPrefix.resource_pool` relationship now points at it. A database migration retroactively consolidates the IP pool ↔ IP prefix relationships.

  **Breaking change for GraphQL clients.** Because `BuiltinIPPrefix.resource_pool` now returns the abstract `CoreIPPool` generic (instead of the concrete `CoreIPAddressPool`), any existing GraphQL queries that selected fields directly under `resource_pool` will need to be updated to use inline fragments for fields that are specific to `CoreIPAddressPool` or `CoreIPPrefixPool`. For example:

  ```graphql
  # Before
  query {
    BuiltinIPPrefix {
      edges { node { resource_pool { edges { node { name { value } default_address_type { value } } } } } }
    }
  }

  # After
  query {
    BuiltinIPPrefix {
      edges { node { resource_pool { edges { node {
        name { value }
        ... on CoreIPAddressPool { default_address_type { value } }
        ... on CoreIPPrefixPool  { default_prefix_type  { value } }
      } } } } }
    }
  }
  ```

  Fields that exist on the `CoreResourcePool` generic (`name`, `description`) can still be selected directly without a fragment.
- Fixed Python transform based computed attributes not being configured after a repository commit update. The trigger template referenced `event.payload['commit']` instead of `event.payload['data']['commit']`; starting with Prefect 3.7 an undefined template reference fails the whole automation action instead of rendering an empty string, so the setup workflow never ran.
- Proposed change action buttons (approve, reject, merge, close, draft) now surface the actual backend error message in the toast instead of a generic "An error occurred" message, making failures easier to diagnose.
- The SSO default group (`sso_user_default_group`) is now only assigned on a user's first login, when their external identity is created. Previously it was re-applied on every login whenever the identity provider returned no group claims, so an administrator who removed a user from the default group would find them added back on their next login. Groups derived from identity-provider claims continue to be synchronized on every login.

### Housekeeping

- Refactored permission system to extract decision logic into a single `PermissionResolver` class. `PermissionManager` now delegates resolution to the resolver and the permission report uses the same resolver, ensuring the GraphQL pipeline and UI report always agree.

## [Infrahub - v1.9.10](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.10) - 2026-07-07

### Fixed

- Fixed the branch merge rollback so that a database error (such as an out-of-memory error) raised
  partway through the merge queries no longer leaves partially merged data on the destination
  branch. The rollback now removes every change stamped with the merge timestamp even when the
  failure occurred before the merge finished writing all of its batches.

## [Infrahub - v1.9.9](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.9) - 2026-06-23

### Security

- Upgraded GitPython to 3.1.50 to address GHSA-mv93-w799-cj2w, a configuration-injection vulnerability that could lead to arbitrary code execution via crafted git config section names.

### Added

- Added a link in the Proposed Change "Checks" tab from each Artifact Validator to the originating `CoreArtifactDefinition`, so users can navigate directly to the definition that produced the check.

### Fixed

- Importing a Git repository now succeeds even when one of its branches has a merge conflict against the default branch. The conflicting branch is imported as-is and a warning is logged; the conflict is reported when a user later attempts to merge the branch. ([#2293](https://github.com/opsmill/infrahub/issues/2293))
- Fixed the unclear error message shown when picking a time earlier than the Infrahub instance was created. ([#4076](https://github.com/opsmill/infrahub/issues/4076))
- Narrowed the git repository lock so it only guards on-disk git working-copy mutations (clone, fetch, worktree creation) and no longer wraps importing repository objects into the graph. ([#6639](https://github.com/opsmill/infrahub/issues/6639))
- Added a refresh button to the artifact detail page so regenerated artifact content can be reloaded in place, without requiring a full browser refresh. ([#9335](https://github.com/opsmill/infrahub/issues/9335))
- Fixed git repository synchronization so that a failure on one branch no longer prevents the other branches from being synchronized. ([#9463](https://github.com/opsmill/infrahub/issues/9463))
- Fixed the file action reported by the repository diff so a file added on a branch is labelled `added` (and a deleted file `removed`) instead of being inverted in `GET /api/diff/files` and the Proposed Change Files tab. ([#9530](https://github.com/opsmill/infrahub/issues/9530))
- Rebasing a branch now only requires the `global:rebase_branch:allow_all` permission. Previously the default-branch permission check ran ahead of the rebase check and also demanded `global:edit_default_branch:allow_all`, so users granted only the rebase permission were denied with "You are not allowed to change data in the default branch". ([#9604](https://github.com/opsmill/infrahub/issues/9604))
- Fixed the repository **Import latest commit** and **Reimport current commit** actions running against `main` instead of the branch currently selected in the UI. ([#9653](https://github.com/opsmill/infrahub/issues/9653))
- Computed attribute updates no longer raise a `ValueError` when `PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES` is set to `1`. The workflow submission chunk size is now floored at 1.
- Concurrent imports of the same repository no longer race to create the same object and fail on a name uniqueness constraint, which could leave the repository out of sync. The graph-changing phase of a repository import is now serialized under the repository lock.
- Repository synchronization now resolves both a new repository's initial import and the pinned worker-pool commit from the repository's Git default branch rather than Infrahub's default branch name, fixing repositories whose Git default branch differs and staging-branch syncs.

## [Infrahub - v1.9.8](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.8) - 2026-06-09

### Changed

- Performance improvements for transform-based computed attributes

### Fixed

- Removing an attribute or relationship from a generic schema now also reconciles `uniqueness_constraints`, `human_friendly_id`, `order_by`, and `default_filter` on inheriting node schemas. Previously a node that inherited a constraint referencing the removed field could end up with an orphaned path, causing a `Requested unique constraint not found within node` exception. ([#5735](https://github.com/opsmill/infrahub/issues/5735)) and ([#8990](https://github.com/opsmill/infrahub/issues/8990))
- Preserve `IPPrefix.utilization` on a newly created branch. The per-branch utilization resolver now considers the branch's full inheritance scope, so prefixes show the same value as their origin branch until data is modified. ([#9220](https://github.com/opsmill/infrahub/issues/9220))
- Fixed repository import so that an object referencing a transform defined in the same repository is resolved correctly instead of failing the import. ([#9406](https://github.com/opsmill/infrahub/issues/9406))
- Scope artifact and Generator regeneration to the changed objects when a definition's GraphQL query filters by a composite, multiple, relationship-based, or human-friendly-id uniqueness constraint. Previously only a single single-attribute uniqueness constraint (or a filter by `ids`) was recognized as targeting a unique object, so these common query shapes fell back to regenerating every target in the group during a proposed change. ([#9486](https://github.com/opsmill/infrahub/issues/9486))
- Fixed overriding a node relationship that was set by a Profile. Peers also provided by the Profile are no longer removed when overriding the relationship; they are kept and become node-defined values.
- Update RelationshipAdd and RelationshipRemove GraphQL mutations so that they properly remove the Profile sourcing of all peers on an updated relationship if that relationship is sourced from a Profile.
- `RelationshipAdd` now correctly rejects requests that supply more than one peer for a cardinality-one relationship.

## [Infrahub - v1.9.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.7) - 2026-06-03

### Breaking Changes

- Schema attribute and relationship names containing `__` are now rejected at load time, since `__` is reserved as the schema path separator. Any existing schema using such names will fail to load after upgrading — rename the affected attributes or relationships in your schema files (and remove or rename the corresponding data) before upgrading. ([#9209](https://github.com/opsmill/infrahub/issues/9209))

### Security

- Added the `INFRAHUB_SECURITY_SSO_ACCOUNT_NAME_FALLBACK` setting (enabled by default) to control whether an SSO login without a linked identity may adopt a pre-existing account that matches by display name. This transitional behavior supports upgrades; disabling it once all SSO users have completed their first login is recommended as a hardening step. The fallback is deprecated and will be removed in a future release.
- Enable cryptographic verification of the OIDC `id_token` (signature, audience and issuer) by default when reading group claims. This can be disabled through `INFRAHUB_OIDC_<PROVIDER>_ID_TOKEN_VERIFY_SIGNATURE`.
- Local password changes are now refused for accounts that authenticate through an external directory (LDAP, OIDC, OAuth2). The self-service form is hidden in the UI and the GraphQL mutation rejects the request, preventing a user from bypassing directory-side revocation by setting a local password.

### Fixed

- Prefix pools no longer allocate the same prefix multiple times when the pool resource has the same prefix length as the requested allocation size. Prefix pools can now correctly allocate a prefix that uses an entire linked resource.
- Fix schema processing crashing with `'NodeSchema' object has no attribute 'get'` when a node defines a single-element relationship-only `uniqueness_constraints` entry (e.g. `[["parent"]]`). ([#4483](https://github.com/opsmill/infrahub/issues/4483))
- The 'Manage Groups' dropdown and the bulk 'Add to groups' toolbar now hide groups whose `group_type` is `internal`, so only user-assignable groups appear in the selector. ([#4872](https://github.com/opsmill/infrahub/issues/4872))
- RelationshipAdd now allows setting a cardinality-one relationship (previously, any attempt was rejected). A second add is rejected when a peer is already present. RelationshipRemove now enforces mandatory constraints on cardinality-many relationships and rejects removals that would leave a mandatory relationship with no peers. ([#5794](https://github.com/opsmill/infrahub/issues/5794))
- GraphQL variables used inside the `data` sub-object of `IPPrefixPoolGetResource` and `IPAddressPoolGetResource` mutations now resolve correctly instead of being silently ignored (set to null). ([#6850](https://github.com/opsmill/infrahub/issues/6850))
- Artifact diffs no longer show spurious changes for artifacts whose schema kind was renamed or moved to a different namespace on a branch. ([#7490](https://github.com/opsmill/infrahub/issues/7490))
- Fixed unique constraints not being enforced on computed attributes, and the violation message now names the input attributes to change. ([#7924](https://github.com/opsmill/infrahub/issues/7924))
- Fix user-check failure logs being emitted one character per line in the proposed change task output — each log entry from `self.log_error(...)` is now rendered as a single warning line. ([#8224](https://github.com/opsmill/infrahub/issues/8224))
- Honor `INFRAHUB_CACHE_TLS_ENABLED`, `INFRAHUB_CACHE_TLS_INSECURE`, and `INFRAHUB_CACHE_TLS_CA_FILE` for the Prefect result storage block. Background flows previously hung in `RUNNING` against TLS-only Redis because `setup_blocks()` constructed the block via a code path that ignored every TLS setting. The block now uses a `redis://` or `rediss://` connection string that propagates all three TLS knobs through `redis.Redis.from_url`, bringing the block into parity with the cache adapter and distributed lock. ([#9217](https://github.com/opsmill/infrahub/issues/9217))
- Fixed git repository sync where multiple task workers could diverge on different commits if upstream advanced during fan-out. ([#9349](https://github.com/opsmill/infrahub/issues/9349))
- Fixed S3 object storage failing with `AuthorizationHeaderMalformed` when no static AWS credentials are configured. When both `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are unset, Infrahub now falls back to the default AWS credential provider chain, so S3 storage works with IRSA, EC2 instance profiles, and ECS task roles in addition to static access keys. Configuring only one of the two now raises a clear configuration error. ([#9429](https://github.com/opsmill/infrahub/issues/9429))
- A failed OIDC `id_token` verification — invalid signature, audience, issuer, or an unresolvable signing key — now returns an authorization error (HTTP 401) instead of an unhandled server error.
- Fixed a crash when pulling a git repository that had to create a missing local branch and record its commit value.
- Fixed the read-only git repository add flow broadcasting the wrong repository kind, which caused peer workers to materialize the new repository as read-write instead of read-only.

## [Infrahub - v1.9.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.6) - 2026-05-20

### Fixed

- Fixed "Copy ID", "Copy HFID", and "Copy Token" actions not working when accessing Infrahub over HTTP (non-secure context). ([#8857](https://github.com/opsmill/infrahub/issues/8857))
- Fix a bug in the merge logic that prevented the merge operation from deleting an object that had its kind or inheritance updated on the default branch after the branch being merged forked. ([#9283](https://github.com/opsmill/infrahub/issues/9283))
- Bump SDK version to 1.20.1 to include fix for retrieving branches in the MERGING status ([sdk#1036](https://github.com/opsmill/infrahub-sdk-python/pull/1036))

## [Infrahub - v1.9.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.5) - 2026-05-18

### Fixed

- Upserting a CoreNumberPool with allow_upsert=True no longer raises an error when node and node_attribute are unchanged. ([#5636](https://github.com/opsmill/infrahub/issues/5636))
- Fixed the standard resolver for schema-based objects returning an unhelpful database error when negative values were provided for limit or offset query arguments. ([#7474](https://github.com/opsmill/infrahub/issues/7474))
- Changing `unique` to `False` on a schema attribute now correctly triggers a migration that adds the attribute to existing profile and template objects. ([#8894](https://github.com/opsmill/infrahub/issues/8894))
- Cardinality constraints (`cardinality: one`, `min_count`, `max_count`) were silently skipped when the relationship being updated declared its peer as a generic and the constraint was defined on a concrete subtype of that generic, letting data violate the schema. The constraint check and lock path now resolve each peer's concrete kind and enforce the constraint declared there. ([#8953](https://github.com/opsmill/infrahub/issues/8953))

## [Infrahub - v1.9.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.4) - 2026-05-12

### Added

- Add a `rebase_branch` global permission so administrators can grant non-admin users the ability to rebase branches without requiring `super_admin`. ([#8050](https://github.com/opsmill/infrahub/issues/8050))

### Fixed

- Fixed inconsistent IPHost and IPNetwork attribute representations across HFID, display labels, and API responses by normalizing values at input time. Added a migration that recomputes HFID/display labels for nodes whose schema references an IPHost, IPNetwork, or MacAddress attribute. ([#8896](https://github.com/opsmill/infrahub/issues/8896))
- Standardized stored MacAddress attribute values to colon-separated EUI-48 form (`AA:BB:CC:DD:EE:FF`) and rebuilt HFIDs / display labels for nodes referencing MAC attributes. ([#9015](https://github.com/opsmill/infrahub/issues/9015))
- Prevent users from deleting their own account through the `CoreAccountDelete` mutation. ([#9138](https://github.com/opsmill/infrahub/issues/9138))
- Remove the unresolvable `is_inherited` field from `AttributeInterface` and all concrete attribute types in the GraphQL schema. The field had no resolver, so any query selecting it failed with `'<AttributeKind>' object has no attribute 'is_inherited'`. ([#9146](https://github.com/opsmill/infrahub/issues/9146))
- Skip artifacts whose `object` peer can no longer be resolved when validating artifact generation in a Proposed Change. A single orphan row no longer prevents `CheckArtifactCreate` from being dispatched for the rest of the group. ([#9188](https://github.com/opsmill/infrahub/issues/9188))
- Fix diff calculation logic to correctly include updates to branch-aware attributes of branch-agnostic schemas. ([#9221](https://github.com/opsmill/infrahub/issues/9221))
- Diff calculation between branches no longer scales with the total size of the database. Diffs now complete in a time proportional to the number of changes on the branch. ([#9224](https://github.com/opsmill/infrahub/issues/9224))
- Reset a Proposed Change's status to "open" following a merge failure that raises an unexpected error.

## [Infrahub - v1.9.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.3) - 2026-05-05

### Fixed

- Increase coverage of rollback protection over merge logic to prevent partially merged branches during unexpected failures ([#9115](https://github.com/opsmill/infrahub/issues/9115))
- Fix a critical race condition where concurrent coroutines in API and task workers could share the same Neo4j async driver session, causing non-deterministic failures including `RuntimeError: read() called while another coroutine is already waiting for incoming data`, hung tasks, and in some cases infinite loops. ([#9121](https://github.com/opsmill/infrahub/issues/9121))

## [Infrahub - v1.9.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.2) - 2026-04-30

### Fixed

- Stop object-type conversion of agnostic nodes with aware attributes from re-opening merged or deleting branches. The "needs rebase" status now only applies to non-terminal branches. ([#9103](https://github.com/opsmill/infrahub/issues/9103))
- Stop `infrahub upgrade` from overwriting the status of merged or deleting branches. Branches in a terminal state (`MERGED`, `DELETING`) are now skipped, so they no longer reappear as `NEED_UPGRADE_REBASE` after an upgrade. ([#9103](https://github.com/opsmill/infrahub/issues/9103))

## [Infrahub - v1.9.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.1) - 2026-04-29

### Added

- Added InfrahubGraphQLQueryReport introspection query to report whether a GraphQL query targets unique nodes for artifact regeneration. ([#IFC-2504](https://github.com/opsmill/infrahub/issues/IFC-2504))

### Fixed

- Fixed a bug where object files in a git commit were imported using a stale schema cache when the same commit also contained schema changes. The schema cache is now refreshed after schema files are imported, ensuring object files are validated against the updated schema. ([#6814](https://github.com/opsmill/infrahub/issues/6814))
- Fixed hierarchy queries returning duplicate parents after merging a branch that changed a node's hierarchical parent. ([#8395](https://github.com/opsmill/infrahub/issues/8395))
- Fixed branch delete permission preventing users from deleting their own branch ([#8528](https://github.com/opsmill/infrahub/issues/8528))
- Fixed attribute migration for sub-template schemas: changing `read_only` or `optional` on a node with `generate_template=False` that is a COMPONENT or PARENT peer of a `generate_template=True` node now correctly updates existing template instances. ([#8722](https://github.com/opsmill/infrahub/issues/8722))
- Fixed git repository registration failing when the working directory contains a `.git` reference pointing to a path that is inaccessible to the process (for example, in containerized setups). ([#9008](https://github.com/opsmill/infrahub/issues/9008))
- Fixed task failures (artifact generation, transforms) that could occur when a recently pushed commit had not yet been fetched locally. ([#9036](https://github.com/opsmill/infrahub/issues/9036))

## [Infrahub - v1.9.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.9.0) - 2026-04-24

### Removed

- Remove proposed change comments created_at and created_by attribute and relationship in favor of already existing node metadata created_by and created_at
- Removed deprecated GraphQL queries and mutations `IPAddressGetNextAvailable`, `IPPrefixGetNextAvailable`, `IPPrefixPoolGetResource`, `IPAddressPoolGetResource`, use their `Infrahub` prefixed equivalents
- Removed previously deprecated "_updated_at" field within GraphQL queries. Use "updated_at" within the node_metadata instead.

### Added

- Added condition to restrict the addition of optional attributes that participate in uniqueness constraints to generated profile schemas ([#7644](https://github.com/opsmill/infrahub/issues/7644))
- Added `display` field to `AttributeSchema` and `RelationshipSchema` with enum values `default` and `extra`, defaulting to `default`. This controls where attributes and relationships are displayed in the UI — `default` shows in the main view, `extra` in an expanded/secondary section.
- Added `infrahub db reset-deployment-id` CLI command to regenerate the internal `deployment_id` without rebuilding the database.
- Added a delete branch modal with the option to also delete the branch from Git
- Added ability to automatically delete branches after a successful merge. When `INFRAHUB_DELETE_BRANCH_AFTER_MERGE` is enabled (default: `False`), the Infrahub branch is deleted. Optionally, when `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE` is also enabled (requires the first setting), the corresponding Git branch is deleted from synced repositories. The `BranchDelete` GraphQL mutation accepts a `delete_from_git` parameter to override the Git deletion setting per request.
- Added an "Extra" toggle button in the object details card to reveal fields marked with display "extra", which are now hidden by default
- Added login and logout activity events (`infrahub.account.logged_in` and `infrahub.account.logged_out`). Successful authentication attempts via password, OAuth2, and OIDC, as well as explicit logouts, are now queryable via the activity event feed.
- Added namespace restriction parameter into generic schemas
- Added optional `description` field for Python transforms in `.infrahub.yml`. Descriptions set in the repository config are propagated to the `TransformPython.description` attribute so they appear in the UI and API.
- Added parent prefix lookup to the search anywhere dialog (Cmd+K). When searching for a valid IP address or CIDR prefix, containing parent prefixes are now displayed in a dedicated "Parent Prefixes" section, ordered from most specific to least specific, across all namespaces. Supports both IPv4 and IPv6.
- Added schema graph visualizer plugin allowing users to view schemas as an interactive graph
- Added support for `graphql_fragments` in `.infrahub.yml`. Repositories can now declare reusable `.gql` fragment files and reference them with standard fragment spread syntax (`...FragmentName`) in query files. Fragment definitions are resolved (including transitive dependencies) and inlined at repository sync time, so the stored query is a self-contained document. The same rendering applies when running queries locally with `infrahubctl`.
- Added support for artifact content composition via Jinja2 filters. Templates running on Prefect workers can now use `artifact_content`, `file_object_content`, `from_json`, and `from_yaml` filters to inline and parse content from other artifacts and file objects. These filters are blocked in computed attributes for security.
- Added support for custom HTTP headers on webhooks. Users can create reusable key-value pairs (static or environment-variable-based) and associate them with webhooks.
- Schema selector search bar is now sticky at the top, with new collapse all and expand all buttons to quickly toggle every namespace section.
- Unified IPAM detail pages with the standard object details card, adding field metadata, extra fields toggle, edit metadata, and profiles & groups
- When `delete_branch_after_merge` is enabled, merging a branch now redirects to the branches list view and switches to the main branch if the deleted branch was the active one. Merging a proposed change stays on the detail page but switches to the main branch if the source branch was the active one.

### Changed

- Accounts, Groups, Roles, and Global Permissions tables in Role Manager now use the same updated design and features as other object tables across the application
- Added a unified filter picker for object list views and support for node metadata filtering:

  - New: Added a unified Filter menu that displays available filters for attributes, relationships and metadata
  - New: Added metadata filters (Created at, Created by, Updated at, Updated by)
  - New: Click an active filter tag to edit it or remove via the inline X
  - Improved: Active filter tags are now editable: click a tag to change its value without removing it
  - Improved: Filter tags now display human-readable conditions (contains, is any of, is empty, before, after etc...)
- Consistent headers across object list and detail pages. Object list pages now share the same header style as detail pages, with easy access to schema, docs, and refresh actions.
- Jinja2 computed attributes are now recalculated immediately when their dependent attributes or relationships change on the same node, eliminating background task overhead for local changes.
- Telemetry snapshots are now always stored locally in the database regardless of the telemetry opt-out setting, ensuring air-gapped and opted-out deployments retain usage data for support and auditing. New CLI commands `infrahubctl telemetry list` and `infrahubctl telemetry export` allow administrators to view and export stored telemetry data. A REST API endpoint `GET /api/telemetry/snapshots` provides programmatic access with `READ_TELEMETRY` permission enforcement.
- `infrahub.branch.deleted` and `infrahub.branch.merged` events now expose the associated proposed change (when applicable) as the event's primary node instead of a related node. Consumers filtering on `primaryNodeIds` will match these events for a proposed change; filters relying on the proposed change appearing under `relatedNodes` must be updated.
- hides the `internal` attributes of CoreFileObject in the UI

### Fixed

- Fix diff update logic that runs after merge and rebase operations to ignore diffs for merged and deleted branches. Add a new environment variable, "INFRAHUB_DIFF_UPDATE_AFTER_MERGE", that allows skipping the automatic diff updates following a merge. ([#8507](https://github.com/opsmill/infrahub/issues/8507))
- Fix a bug in diff calculation that could cause the wrong peer to be identified for a peer object belonging to a schema that had its kind or inheritance updated on the default branch.
- Fix bug in diff calculation that would cause source property update on the user-created branch to be ignored if the schema of the owning object was migrated to a new kind or inheritance on the default branch.
- Fix bug in diff calculation that would not correctly capture conflicts if the source of an attribute or relationship was updated to conflicting values on the default branch and the user-created branch.
- Fix clicking on kinds in the schema viewer modal to navigate to the related schema.
- Fix identifier not being returned when querying number pool allocations via GraphQL API.
- Fixed pagination offset being ignored when querying InfrahubBranch
- Fixed possible empty display labels by removing legacy display_labels processing
- Improve SVG artifact handling: allow scrolling in the preview so oversized content is no longer clipped, and fix the download action so the saved file contains the raw SVG content.
- Object table now refreshes automatically after adding or removing objects from groups in bulk
- Suppress spurious Neo4j SCHEMA notifications for optional relationship types that do not yet exist in the database schema, eliminating noisy log warnings about non-existent HAS_OWNER and HAS_SOURCE relationship types.

### Housekeeping

- Removed deprecated forwardRef usage across frontend components ([#INFP-560](https://github.com/opsmill/infrahub/issues/INFP-560))

## [Infrahub - v1.8.6](https://github.com/opsmill/infrahub/tree/infrahub-v1.8.6) - 2026-04-21

### Changed

- SSO authentication now anchors account identity on the provider-issued `sub` claim rather than the user display name. Existing accounts are linked transparently on first login after upgrade. If a display name collision occurs with another SSO user's account, the email address is used as the account name instead.

### Fixed

- Schema deletions are now rejected when a generic is still referenced by another node's `inherit_from`, and partial schema writes are rolled back if loading the updated schema fails. ([#8988](https://github.com/opsmill/infrahub/issues/8988))
- Fix branch name display in event details popover for branch deletion events.
- Fix check messages overflowing outside their container in proposed changes.

## [Infrahub - v1.8.5](https://github.com/opsmill/infrahub/tree/infrahub-v1.8.5) - 2026-04-17

### Fixed

- Ensure that changes to a password attribute counts as a mutation event for a node. ([#6909](https://github.com/opsmill/infrahub/issues/6909))
- Add distributed lock around branch creation to prevent race condition ([#8368](https://github.com/opsmill/infrahub/issues/8368))
- Correct the display label on events sent from the mutations to update computed attributes and HFIDs when the display label contains attributes from related nodes. ([#8837](https://github.com/opsmill/infrahub/issues/8837))
- Fix false-positive conflict detection during git sync caused by naive string matching of conflict markers in file content. ([#8848](https://github.com/opsmill/infrahub/issues/8848))
- Prevent non-idempotent behavior when loading a schema that involves generic inheritance, HFIDs, uniqueness constraints, and unique attributes. In certain circumstances these elements could interact to cause unexpected schema drift when an attribute was identified as unique from a single-item uniqueness constraint on a node or generic schema. The schema loading logic is updated to ensure all of these elements are idempotent going forward. ([#8897](https://github.com/opsmill/infrahub/issues/8897))
- Fixed git sync not importing objects after repository re-clone from a missing local directory ([#8930](https://github.com/opsmill/infrahub/issues/8930))
- Fixed Jinja2 computed attributes, display labels, and human-friendly IDs failing when referencing attributes on a hierarchical relationship's concrete peer type ([#8943](https://github.com/opsmill/infrahub/issues/8943))
- Fix bug in schema remove migration that could cause removed instances of the schema to be excluded from the diff. Would not cause a functional issue because the schema remove migration would run on the default branch when merged.
- Support non-UTC timezones in filters for GraphQL queries

## [Infrahub - v1.8.4](https://github.com/opsmill/infrahub/tree/infrahub-v1.8.4) - 2026-04-02

### Fixed

- Link a merging proposed change to its diff during the merge operation if it has not been linked yet ([#8769](https://github.com/opsmill/infrahub/issues/8769))
- Fixed an issue where webhook match statements (node kind filters) were lost during scheduled reconfiguration. ([#8772](https://github.com/opsmill/infrahub/issues/8772))

## [Infrahub - v1.8.3](https://github.com/opsmill/infrahub/tree/infrahub-v1.8.3) - 2026-03-31

### Fixed

- Corrected data diff view within a proposed change or branch view so that changes to profiles show up. ([#8529](https://github.com/opsmill/infrahub/issues/8529))
- Fixed hard failures on GraphQL queries that would exhaust Neo4j's server thread pool by implementing backoff retry. ([#8696](https://github.com/opsmill/infrahub/issues/8696))
- Fix object creation from a template when a resource pool is assigned to a required relationship or attribute field. ([#8701](https://github.com/opsmill/infrahub/issues/8701))
- Deleting a node that inherits from `CoreArtifactTarget` now automatically deletes its associated artifacts. ([#8735](https://github.com/opsmill/infrahub/issues/8735))
- Add missing `hfid` field to `RelatedIPAddressNodeInput` GraphQL type, allowing IP address relationships to be referenced by human-friendly ID
- Fixed "Import latest commit" action crashing with `'Node' object has no attribute 'ref'` when used on a regular Repository instead of a Read-Only Repository.

### Housekeeping

- Migrated Node.js from version 22 to 24 LTS across CI workflows, Docker build, and package engine constraints.

## [Infrahub - v1.8.2](https://github.com/opsmill/infrahub/tree/infrahub-v1.8.2) - 2026-03-25

### Changed

- This change prevents redundant artifact regenerations by only triggering on node changes that affect fields actually read by the associated GraphQL query, reducing the number of artifacts that need to be regenerated and speeding up the pipeline.

### Fixed

- Fix scheduled reconfiguration of webhooks targeting "all" events ([#8694](https://github.com/opsmill/infrahub/issues/8694))
- Fixed branch rebase conflicts during 1.7 to 1.8 upgrades caused by migration 056 writing unrelated schema attributes to branch timelines

## [Infrahub - v1.8.1](https://github.com/opsmill/infrahub/tree/infrahub-v1.8.1) - 2026-03-19

### Added

- Added schema processing to schema integrity check in order to validate the schema ([#8355](https://github.com/opsmill/infrahub/issues/8355))

### Fixed

- Prevent multiple merge operations from running simultaneously, whether they are for the same branch or different branches. Only a single merge operation can run at a given time. Before executing any updates, the merge operation will check if the branch being merged is open to prevent merging a branch multiple times. ([#6794](https://github.com/opsmill/infrahub/issues/6794))
- Fixed read-only repository operational status after successful sync ([#8166](https://github.com/opsmill/infrahub/issues/8166))
- Fixed artifact detail page not being accessible when the artifact failed to generate ([#8394](https://github.com/opsmill/infrahub/issues/8394))
- Fixed long branch names overflowing in the branch selector and ensured the branch creation button maintains its size when disabled ([#8629](https://github.com/opsmill/infrahub/issues/8629))

## [Infrahub - v1.8.0](https://github.com/opsmill/infrahub/tree/infrahub-v1.8.0) - 2026-03-16

We're excited to announce the release of Infrahub, v1.8.0!

This release introduces a file objects feature, adds stronger branch life-cycle controls with automatic freeze-on-merge, and adds support for resource pools in object templates. The Infrahub Backup tool now fully supports Kubernetes deployments.

## Main changes

### File Object: Upload and attach files to Infrahub objects

Infrahub can now store files -- Text files, PDFs, images, spreadsheets, KMZ files, and any other format -- directly as objects in the database. With the new `CoreFileObject` generic, you can define custom file types in your schema. Object files behave as all other objects in Infrahub, you can fully customize the schema and relate (or attach) them to other objects.

The contents of the file will be rendered in Infrahub's web interface, if the file has one of the following file types: 

- application/json
- application/yaml
- application/x-yaml
- application/hcl
- application/graphql
- application/pdf
- image/svg+xml
- text/plain
- text/markdown
- application/xml
- text/csv;
- image/png
- image/jpeg
- image/gif
- image/webp
- image/bmp
- image/x-icon

To use this feature, create a schema node that inherits from `CoreFileObject`:

```yaml
nodes:
  - name: ContractDocument
    namespace: Custom
    inherit_from:
      - CoreFileObject
    attributes:
      - name: contract_number
        kind: Text
```

The `CoreFileObject` generic automatically provides read-only attributes for file metadata: `file_name`, `checksum` (SHA-1), `file_size`, `file_type` (MIME type), and `storage_id`.

**Upload** files through GraphQL mutations -- a `file` argument is automatically added to Create, Update, and Upsert mutations for any node inheriting from `CoreFileObject`.

**Download** files through the UI or these REST API endpoints:
- `/api/files/{node_id}` -- by node UUID
- `/api/files/by-hfid/{kind}` -- by human-friendly ID
- `/api/files/by-storage-id/{storage_id}` -- by internal storage ID

The maximum file size defaults to 50 MB and is configurable via the `INFRAHUB_STORAGE_MAX_FILE_SIZE` environment variable.

### Freeze branch after merge

When a branch is merged -- either through a direct branch merge or via a Proposed Change -- it now transitions to a frozen state where no further mutations are allowed. This prevents a class of data integrity issues that could occur when a branch was modified or merged a second time after its initial merge.

Both the backend API and the frontend UI enforce this freeze:
- GraphQL mutations (Create, Upsert, Update, Delete) are blocked on merged branches
- The UI disables editing controls and shows a visual indication that the branch is frozen
- Creating a new Proposed Change for an already-merged branch is prevented

### Resource pool references in object templates

Object templates can now reference resource pools (IP Address, IP Prefix, and Number pools). Previously, adding a resource pool to a template would allocate a resource to the template itself -- not the intended behavior. In 1.8, pool references on templates are stored as metadata. When an object is created from the template, the resource is allocated from the specified pool at creation time.

This applies to all pool types:
- IP Address pools
- IP Prefix pools
- Number pools

The feature introduces a new `relationship_properties` field in the GraphQL schema for template relationships, which stores the pool source reference alongside the standard `edges` field. Template inheritance (subtemplates) correctly propagates pool references.

A database migration is included to convert any existing template-IP relationships that incorrectly have pool sources into the new `_from_resource_pool` relationship format.

### Consult the diff of a proposed change after branch deletion

The data and schema diff of a Proposed Change is now preserved and accessible even after the associated branch has been deleted. This is essential for audit and compliance workflows -- during incident investigation or regulatory review, users need to inspect what changes were made, by whom, and when, regardless of whether the source branch still exists.

The diff data is now tied to the Proposed Change itself rather than solely to the branch. The Files and Artifacts tabs on a Proposed Change also handle deleted branches gracefully, showing a user-friendly message instead of an error.

This feature is a prerequisite for a future capability to automatically delete branches after merge, which will help prevent stale branches that can cause Git synchronization issues.

### Read-only repository: Update to Latest button

Managing read-only Git repositories is now simpler. A new "Update to Latest" button fetches and imports the latest commit from the tracked branch directly from the UI. Previously, users had to manually copy and paste commit hashes from an external source to update what Infrahub was tracking. The existing reimport action has been renamed to "Reimport Current Commit" to clearly distinguish between re-processing the current commit and pulling the latest.

Repositories now also support providing a Git Tag as the reference (ref) to track for a repository.

### Infrahub Backup: Kubernetes support

The `infrahub-backup` CLI tool now fully supports Kubernetes deployments for both backup and restore operations. The tool automatically detects whether Infrahub is running on Docker Compose or Kubernetes and adjusts its behavior accordingly.

For Kubernetes deployments we can now install `infrahub-backup` using the Infrahub Helm Chart. This is now the recommended installation method for Kubernetes deployments.
See the [installation instructions](https://docs.infrahub.app/backup/guides/install#enable-via-infrahub-helm-chart-recommended) for more details

Key new capabilities:
- `infrahub-backup create --k8s-namespace <namespace>` -- creates a backup archive containing Neo4j and PostgreSQL database dumps
- `infrahub-backup restore <backup_file> --k8s-namespace <namespace>` -- restores from an archive, handling service stop/start, cache/queue cleanup, database restore, and service restart automatically
- Supports Neo4j Enterprise Edition online backups
- Backup archives include metadata with Infrahub version, Neo4j edition, components backed up, and timestamps

### Display artifact count in proposed changes

The Proposed Changes detail view now displays item counts on all tabs, giving you immediate visibility into how many changes exist in each category:

- **Data** -- count of added, updated, and removed nodes
- **Files** -- total count of changed files across repositories
- **Artifacts** -- count of changed artifacts (excludes unchanged)
- **Schema** -- count of schema changes
- **Checks** -- count of validators
- **Tasks** -- count of related tasks

### Branch list page improvements

The branch list page continues to evolve with richer information and better usability:

- **Created By** column shows who created each branch (available for branches created after 1.7)
- **Proposed Changes** column links directly to associated proposed changes
- **Status** column shows branch state with warning indicators (e.g., "Rebase needed")
- **Schema Changes** indicator shows whether the branch includes schema modifications
- **Last Rebase** timestamp for sync tracking
- **Merged badge** clearly identifies branches that have been merged
- Merged branches are filtered from the proposed change creation form

### General UI improvements

Several smaller improvements enhance the day-to-day experience:

- **Schema field shortcuts** -- clicking an attribute or relationship label in the object detail view opens the schema viewer modal, scrolling directly to the relevant field definition
- **Field type icons** -- icons next to field names indicate the attribute type (text, number, boolean) and relationship schema
- **Diff status badges** -- file and artifact diffs now show badges indicating the type of change (added, removed, updated)
- **Branch artifacts tab** -- view artifact changes directly from the branch details view
- **Refresh button** -- task list and details views now include a manual refresh button with a tooltip showing the last data refresh time
- **Consistent focus outlines** -- improved visual accessibility across all interactive elements

## Infrahub Python SDK

Infrahub v1.8.0 requires the usage of infrahub-sdk v1.19.0, please update the `infrahub-sdk` package accordingly.

Notable SDK changes in this release:
- Added support for the File Object feature
- Fixed an issue where the SDK tracking feature would fail when deleting a parent node with component relationships (e.g., a device with interfaces). The SDK now correctly handles cascade deletions where component nodes are automatically removed when their parent is deleted, preventing "Unable to find the node" errors in generator workflows.

## Full changelog

### Added

- Added the ability to also fetch tags from git ([#8078](https://github.com/opsmill/infrahub/issues/8078))
- Added `Builtin` to the list of restricted namespaces
- Added `CoreFileObject` generic for storing files as node attributes with branch-aware versioning. Nodes inheriting from `CoreFileObject` support file upload via GraphQL mutations and download via REST API endpoints.
- Added a refresh button to the task list and details view with a tooltip showing the last data refresh time
- Added a shortcut in the object details view: clicking an attribute or relationship label opens the schema viewer modal, directly showing and scrolling to the relevant field definition
- Added ability to view artifact changes from the branch details view
- Added consistent focus outline color across all interactive elements for improved visual accessibility
- Added counts to proposed change tabs
- Added icons next to field names in the object details view to indicate field types (e.g., text, number, boolean) and relationship schemas
- Added status badges to file and artifact diffs showing the type of change (added, removed, updated)
- Added tooltip over action buttons (download/copy) on artifact details view.

### Changed

- Improved consistency of GraphQL Query details page with other object views
- Remove "Task Overview" title from embedded task tabs (object that inherit from CoreTaskTarget)
- Simplified default branch view by hiding inapplicable actions and tabs
- Use Jinja2 templates to compute display labels of permission objects, also mark `identifier` as deprecated

### Fixed

- Handle schema updates and associated data migrations as a single item so that an unexpected failure during a schema migration does not leave the schema and data in incompatible states. This applies to loading a schema, merging a branch, and rebasing a branch. ([#6948](https://github.com/opsmill/infrahub/issues/6948))
- Fixed IP addresses disappearing from their parent prefix when the address mask is less specific than the prefix length ([#7267](https://github.com/opsmill/infrahub/issues/7267))
- Fixed missing changelog events for objects created as side effects during node creation, including pool-allocated resources and template-generated child objects. ([#7268](https://github.com/opsmill/infrahub/issues/7268))
- Allow List attributes to use the regex parameter for validating list item values ([#7717](https://github.com/opsmill/infrahub/issues/7717))
- Fixed schema loading crash when a node with `generate_template=True` has a Component relationship to `CoreNumberPool` ([#7903](https://github.com/opsmill/infrahub/issues/7903))
- Prevent creating multiple number pools for the same schema if it is separately loaded on multiple branches. It is now possible to encounter an error if a user tries to create an instance of a schema immediately after an update to include a NumberPool attribute because the associated CoreNumberPool must be created by an asynchronous task. ([#8222](https://github.com/opsmill/infrahub/issues/8222))
- Shift-click range selection now anchors to the last clicked row, with added e2e coverage for range toggling. ([#8229](https://github.com/opsmill/infrahub/issues/8229))
- Fixed display labels showing 'None' for relationship-based fields after upsert.
  Relationship peer attributes needed by display label and HFID templates are now correctly loaded during node updates. ([#8237](https://github.com/opsmill/infrahub/issues/8237))
- Fixed error reporting on invalid Jinja2 templates for display_labels ([#8311](https://github.com/opsmill/infrahub/issues/8311))
- Removed `generate_template` on a GenericSchema, this attribute could lead to an invalid GraphQL schema and breaking both frontend and backend operations ([#8371](https://github.com/opsmill/infrahub/issues/8371))
- Fix IPAM view failing to load when more than 40 IP namespaces exist. ([#8481](https://github.com/opsmill/infrahub/issues/8481))
- Fix diff update logic that runs after merge and rebase operations to ignore diffs for merged and deleted branches. Add a new environment variable, "INFRAHUB_DIFF_UPDATE_AFTER_MERGE", that allows skipping the automatic diff updates following a merge. ([#8507](https://github.com/opsmill/infrahub/issues/8507))
- Fixed incorrect merge behavior where removing the source property from an attribute was silently ignored during branch merge. ([#8583](https://github.com/opsmill/infrahub/issues/8583))
- Data tables now display error messages when API requests fail due to permission or other errors.
- Fix false "unsaved changes" warning when editing objects with generic relationships.
- Fix task view showing "Name not found" for related nodes that exist only on a branch by querying the correct branch and time context.
- Fixed adding a relationship from a resource pool within relationship tabs in the object detail view
- Show a user-friendly message in the Files and Artifacts tabs of a proposed change when the source branch has been deleted.

## [Infrahub - v1.7.7](https://github.com/opsmill/infrahub/tree/infrahub-v1.7.7) - 2026-03-12

### Fixed

- Fixed display labels showing 'None' for relationship-based fields after upsert.
  Relationship peer attributes needed by display label and HFID templates are now correctly loaded during node updates.
  Includes a migration to correct objects that had their display labels and or human-friendly IDs improperly updated to include a null value. ([#8237](https://github.com/opsmill/infrahub/issues/8237))

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
