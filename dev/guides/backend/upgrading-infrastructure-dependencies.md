# Upgrading infrastructure dependencies

> Part of: `dev/guides/backend/` | Related:
> [`/upgrade-backend-dependencies`](../../../.agents/commands/upgrade-backend-dependencies.md),
> [`/cut-release`](../../../.agents/commands/cut-release.md), [Git Workflow](../../guidelines/git-workflow.md)

An upgrade of Neo4j, Prefect, Redis, RabbitMQ, PostgreSQL or NATS is not complete when this
repository is done. Two other repositories pin the same versions or configure the same services:

- `opsmill/infrahub-private`: builds Infrahub Enterprise. Its invoke tasks, Docker Compose files
  and CI pin the same images as this repository, and its Docker Compose files hold their own
  Prefect settings.
- `opsmill/infrahub-helm`: holds the Helm charts that deploy Infrahub on Kubernetes. It pins the
  Neo4j and Prefect server charts and holds the Prefect settings of these deployments.

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

## Open the pull requests in the other repositories

Open them when you open the Infrahub pull request, and add their links to its description.

### `opsmill/infrahub-private`

- Neo4j, Redis, RabbitMQ, PostgreSQL, NATS: change the same image tags as in this repository. They
  are in `tasks/shared.py`, `docker-compose.yml`, `development/docker-compose-deps.yml` and, for
  Neo4j, `.github/workflows/ci.yml`. Search for the old tag to find each one, for example
  `git grep -n 'neo4j:2026.05.0'`.
- Prefect: there is no pin to change, because `infrahub-private` takes Prefect from the
  `community` submodule. Compare its Prefect settings with the release notes: they are in
  `docker-compose.yml` and in the size presets `docker-compose.small.yml`,
  `docker-compose.medium*.yml` and `docker-compose.large*.yml`. Check its code that uses Prefect
  too, for example the Enterprise task worker, which extends the Infrahub task worker.

### `opsmill/infrahub-helm`

- Neo4j: change the `neo4j` chart version in `charts/infrahub/Chart.yaml`.
- Prefect: compare the Prefect settings with the release notes, and change the ones the new
  version affects. They are in `charts/infrahub/values.yaml` (the task worker environment and the
  `prefect-server` section) and in every values file of `charts/infrahub-enterprise/`. The size
  presets there (`values.small.yaml`, `values.medium*.yaml`, `values.large*.yaml`) run the Prefect
  web server and the Prefect background services as separate deployments. Check also whether the
  new version needs a newer `prefect-server` chart in `charts/infrahub/Chart.yaml`. The release
  process updates the Prefect server image tag (`prefectTag`) on its own. When nothing has to
  change, say so in the Infrahub pull request.
- Redis, RabbitMQ, PostgreSQL, NATS: not decided, ask a maintainer. The chart installs them from
  separate Helm charts, and its Redis and RabbitMQ image versions already differ from the Docker
  Compose ones.

## Merge the other pull requests with the release that ships the upgrade

A pull request in another repository must ship in the same Infrahub release as the Infrahub pull
request, not in an earlier one that was not tested with it. When it has to wait, open it as a
draft and name the Infrahub release it waits for in its description.

- `opsmill/infrahub-helm`: target `stable`, its only main branch. Every final release of Infrahub
  and of Infrahub Enterprise publishes its chart from `stable`, so merge the pull request while
  you cut the Infrahub release that contains the upgrade, before you publish that release. Merged
  earlier, it ships with a release that was not tested with it. Merged later, the charts of the
  release do not contain it. [`/cut-release`](../../../.agents/commands/cut-release.md) has this
  step.
- `opsmill/infrahub-private`: target the branch with the same name as the base of the Infrahub
  pull request. While this repository has a `release-x.y` branch that `infrahub-private` does not
  have, `develop` in `infrahub-private` still holds release x.y, so a change for `develop` waits
  until x.y is released.

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
    Infrahub image built from the upgrade branch.
- High availability on Kubernetes: deploy the example from the
  [high-availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx)
  with the new version, and test it by hand. It runs a Neo4j cluster and the split Prefect
  deployments, and no CI job deploys it.
  - Neo4j: the example turns off the Neo4j of the Infrahub chart and installs the `neo4j/neo4j`
    chart directly, so use the chart version of this pull request, from the high-availability
    guide or `development/deploy.tf`.
  - Prefect: install the charts from the branch of the `infrahub-helm` pull request instead of the
    published ones. The `tests/README.md` of `infrahub-helm` describes how its tests install the
    local charts.
