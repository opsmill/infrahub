# Upgrading infrastructure dependencies

> Part of: `dev/guides/backend/` | Related:
> [`/upgrade-backend-dependencies`](../../../.agents/commands/upgrade-backend-dependencies.md),
> [`/cut-release`](../../../.agents/commands/cut-release.md), [Git Workflow](../../guidelines/git-workflow.md)

An upgrade of Neo4j, Prefect, Redis, RabbitMQ, PostgreSQL or NATS is not complete when this
repository is done. Two other repositories pin the same versions or configure the same services,
and the `AGENTS.md` of each one says what to change there and when its pull request can merge:

- `opsmill/infrahub-private`
  ([AGENTS.md](https://github.com/opsmill/infrahub-private/blob/stable/AGENTS.md)): builds
  Infrahub Enterprise.
- `opsmill/infrahub-helm` ([AGENTS.md](https://github.com/opsmill/infrahub-helm/blob/stable/AGENTS.md)):
  holds the Helm charts that deploy Infrahub on Kubernetes.

Read that `AGENTS.md` before you change the repository, because an agent that works from this
repository does not always load it. Open these pull requests when you open the Infrahub one, and
add their links to its description.

[`/upgrade-backend-dependencies`](../../../.agents/commands/upgrade-backend-dependencies.md) lists
the files to change in this repository. It does not cover Prefect. Find the Prefect pins, including
`prefect-redis`, with the first command below, then run `uv lock` in the repository root and in
`python_testcontainers/`. The second command finds the comments and links that name the current
version: check that what they say is still true for the new version.

```bash
git grep -nE 'prefect(-client|-redis)?==|prefecthq/prefect:'
git grep -nF '<current version>' -- ':!*.lock' ':!CHANGELOG.md' ':!docs/docs/release-notes'
```

## Target `develop` for Neo4j and Prefect

Open a Neo4j or Prefect upgrade against `develop`, so it ships in a feature release and not in a
patch release. CI does not run the tests these upgrades need (see
[Run the tests that CI does not run](#run-the-tests-that-ci-does-not-run)), and Prefect patch
releases can contain breaking changes.

## Merge the other pull requests with the same release

A pull request in another repository must ship in the same Infrahub release as the Infrahub one,
not in an earlier release that was not tested with it, so it often waits as a draft. Name that
release in its description, and change it if the Infrahub pull request moves to a later release.
The `AGENTS.md` of its repository says when it can merge, and
[`/cut-release`](../../../.agents/commands/cut-release.md) merges the waiting `infrahub-helm` ones.

## Run the tests that CI does not run

A Neo4j or Prefect upgrade is ready to merge only after these two runs. Run them, or ask a
maintainer to, and post the results on the Infrahub pull request.

- Performance: run the tests in `opsmill/infrahub-private-tests` with the new version and with the
  current one, on the same datasets, and compare the failures and the durations. Check in the
  output of each run that it used the version you meant to test:
  - Neo4j: the test containers start the Neo4j image that the installed `infrahub-testcontainers`
    release pins, unless `NEO4J_DOCKER_IMAGE` is set. A cluster deployment reads
    `DATABASE_DOCKER_IMAGE` instead.
  - Prefect: the task manager of the test stack runs the Infrahub image, so run the tests on an
    Infrahub image built from the upgrade branch. The test containers take it from
    `INFRAHUB_TESTING_DOCKER_IMAGE` and `INFRAHUB_TESTING_IMAGE_VERSION`.
- High availability on Kubernetes: deploy the example from the
  [high-availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx)
  and test it by hand. It runs a Neo4j cluster and the split Prefect deployments, and no CI job
  deploys it. Its values pin an older Infrahub image, so set `infrahubTag` and `prefectTag` to an
  image built from the upgrade branch.
  - Neo4j: the example turns off the Neo4j of the Infrahub chart and installs the `neo4j/neo4j`
    chart directly, so use the chart version of this pull request, from the high-availability
    guide or `development/deploy.tf`.
  - Prefect: install the charts from the branch of the `infrahub-helm` pull request instead of the
    published ones, as its `AGENTS.md` describes.
