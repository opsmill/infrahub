# Upgrading infrastructure dependencies

> Part of: `dev/guides/backend/` | Related:
> [`/upgrade-backend-dependencies`](../../../.agents/commands/upgrade-backend-dependencies.md),
> [Git Workflow](../../guidelines/git-workflow.md)

An upgrade of Neo4j, Prefect, Redis, RabbitMQ, PostgreSQL or NATS is not complete when this
repository is done. Two other repositories pin the same versions or configure the same services:

- `opsmill/infrahub-private`: builds Infrahub Enterprise. Its invoke tasks, Docker Compose files
  and CI pin the same images as this repository.
- `opsmill/infrahub-helm`: holds the Helm charts that deploy Infrahub on Kubernetes. It pins the
  Neo4j chart and holds the Prefect configuration of these deployments, including the size
  presets of the Enterprise chart.

[`/upgrade-backend-dependencies`](../../../.agents/commands/upgrade-backend-dependencies.md) lists
the files to change in this repository. It does not cover Prefect: find every place that names the
current Prefect version with `git grep -nF`, for example `git grep -nF '3.8.6'`, then run `uv lock`
in the repository root and in `python_testcontainers/`. Where a comment names the version, check
that what it says is still true for the new version.

## Target `develop` for Neo4j and Prefect

Open a Neo4j or Prefect upgrade against `develop`, so it ships in a feature release and not in a
patch release. CI does not run the tests these upgrades need (see
[Run the tests that CI does not run](#run-the-tests-that-ci-does-not-run)), and Prefect patch
releases can contain breaking changes.

## Open the pull requests in the other repositories

Open them when you open the Infrahub pull request, and list them in its description.

### `opsmill/infrahub-private`

- Neo4j, Redis, RabbitMQ, PostgreSQL, NATS: change the same image tags as in this repository. They
  are in `tasks/shared.py`, `docker-compose.yml`, `development/docker-compose-deps.yml` and, for
  Neo4j, `.github/workflows/ci.yml`. Search for the old tag to find each one, for example
  `git grep -n 'neo4j:2026.05.0'`.
- Prefect: there is no pin to change, because `infrahub-private` takes Prefect from the
  `community` submodule. Check its code that uses Prefect against the release notes, for example
  the Enterprise task worker, which extends the Infrahub task worker.

### `opsmill/infrahub-helm`

- Neo4j: change the `neo4j` chart version in `charts/infrahub/Chart.yaml`.
- Prefect: compare the Prefect settings with the release notes, and change the ones the new
  version affects. They are in `charts/infrahub/values.yaml` (the task worker environment and the
  `prefect-server` section) and in the size presets in `charts/infrahub-enterprise/`
  (`values.small.yaml`, `values.medium*.yaml`, `values.large*.yaml`), which run the Prefect web
  server and the Prefect background services as separate deployments. The release process
  updates the Prefect server image tag (`prefectTag`) on its own. When no setting has to change,
  say so in the Infrahub pull request instead.
- Redis, RabbitMQ, PostgreSQL, NATS: not decided, ask a maintainer. The chart installs them from
  separate Helm charts, and its Redis and RabbitMQ image versions already differ from the Docker
  Compose ones.

## Merge the other pull requests when their branch matches the release

A pull request in another repository can merge only when its target branch is for the same
Infrahub release as the Infrahub pull request. When it has to wait, open it as a draft and name the
Infrahub release it waits for in its description.

- `opsmill/infrahub-helm`: target `stable`, its only main branch. Every final Infrahub release,
  patch releases included, publishes the `infrahub` chart from `stable`, so a chart change merged
  early ships with the next release even if that release was not tested with it. Merge it after
  the Infrahub release that contains the upgrade is out.
- `opsmill/infrahub-private`: target the branch with the same name as the base of the Infrahub
  pull request. While this repository has a `release-x.y` branch that `infrahub-private` does not
  have, `develop` in `infrahub-private` still holds release x.y, so a change for `develop` waits
  until x.y is released.

## Run the tests that CI does not run

A Neo4j or Prefect upgrade is ready to merge only after these two runs. Run them, or ask a
maintainer to, and post the results on the Infrahub pull request.

- Performance: run the tests in `opsmill/infrahub-private-tests` with the new version and with the
  current one, on the same datasets, and compare the failures and the durations. The test
  containers start the Neo4j image that the installed `infrahub-testcontainers` release pins unless
  `NEO4J_DOCKER_IMAGE` is set, so set it to the new image, or the run tests the old version.
- High availability on Kubernetes: deploy the setup from the
  [high-availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx)
  with the new version and the `infrahub-helm` changes, and test it by hand. This setup runs a
  Neo4j cluster and the split Prefect deployments, and no CI job deploys it.
