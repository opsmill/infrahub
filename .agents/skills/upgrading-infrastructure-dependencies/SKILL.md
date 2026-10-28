---
name: upgrading-infrastructure-dependencies
description: >-
  Upgrades Neo4j, Prefect, Redis, RabbitMQ, PostgreSQL or NATS across opsmill/infrahub,
  opsmill/infrahub-private and opsmill/infrahub-helm, including the tests that CI does not run.
  TRIGGER when: the user wants to upgrade or bump one of these services, the prefect package, or
  the Neo4j image or Helm chart, or to check or finish such an upgrade. DO NOT TRIGGER when:
  bumping an ordinary Python or JavaScript package that is not one of these services; analyzing
  what a dependency-bump pull request breaks → analyzing-dependency-bumps.
argument-hint: <service and target version, for example "neo4j 2026.09.0">
compatibility: Requires push access to opsmill/infrahub, opsmill/infrahub-private and opsmill/infrahub-helm, GitHub access to open pull requests, and network access to the release notes and Docker Hub.
metadata:
  version: 0.1.0
  author: OpsMill
---

# Upgrading infrastructure dependencies

One upgrade of these services can need a pull request in three repositories:

- `opsmill/infrahub` (this repository): the Docker Compose stack, the test containers, the tests,
  the docs and the Python packages.
- `opsmill/infrahub-private`: Infrahub Enterprise. It pins some of the same images, and its tests
  must pass with the new version too.
- `opsmill/infrahub-helm`: the Helm charts.

Read the `AGENTS.md` of each repository before you change it. The
[service notes](#service-notes) at the end say what is specific to each service.

## 1. Agree on the scope and the release

Ask the user which services to upgrade and to which version. Never default to all of them.

Then find the Infrahub release that the upgrade ships in, and confirm it with the user. It is the
release that `develop` holds: the minor release after the latest release tag
(`git ls-remote --tags origin 'infrahub-v*'`), or the one after that when a `release-x.y` branch
already holds that next minor release. For example, with `infrahub-v1.11.9` as the latest tag and
a `release-1.12` branch, the upgrade ships in 1.13.0. Infrahub Enterprise uses the same numbers.

## 2. Check what the new version changes

Read the release notes of every version between the current one and the target, not only the
target: breaking changes often sit in the versions in between. For each change that can reach
Infrahub, find the code or setting it touches and decide how to check it. Show the user a short
report (the breaking changes, the deprecated features that Infrahub uses, the code or setting
changes needed, whether the client library supports the new version, and the risk). Wait for their
go before you change anything.

## 3. Branch from the right base

- `opsmill/infrahub` and `opsmill/infrahub-private`: branch from `develop`. Neo4j and Prefect
  upgrades ship in a feature release and never in a patch release, also for a patch version of
  either, because CI does not run the tests they need and Prefect patch releases can contain
  breaking changes.
- `opsmill/infrahub-helm`: branch from `stable`, its only main branch.

## 4. Change this repository

Search for the old version and change every pin that the search finds, except the files that
record past changes and `.github/workflows/version-upgrade.yml`, whose images are the versions that
the upgrade test starts from:

```bash
git grep -nF '<old tag>' -- ':!CHANGELOG.md' ':!changelog' ':!docs/docs/release-notes' \
  ':!dev/specs' ':!docs/archive' ':!.github/workflows/version-upgrade.yml'
```

The service notes give a better search for Neo4j and Prefect. Add a changelog fragment of type
`changed` with the `creating-changelog-entries` skill, and run the checks that `AGENTS.md` lists
before you push.

## 5. Open the Infrahub pull request

Open it as a draft against `develop` with the `pr` skill, with the title
`chore(deps): upgrade <service> from <old version> to <new version>`. In the description, write
the release it ships in, each change in the release notes that can reach Infrahub and how you
checked it, what you did not test, the pull requests in the other repositories, and the test
results of steps 6 and 7 as they come in.

## 6. Change the other two repositories

Search there for the old version too. Show the user the changes, and open the pull requests only
after they agree, as drafts that link the Infrahub pull request and name the release the upgrade
ships in.

- `opsmill/infrahub-private`: its tests must pass with the new version before the Infrahub pull
  request merges. Run them with `community` at the upgrade branch, as its `AGENTS.md` describes,
  and post the result on the Infrahub pull request. A pull request there merges after the Infrahub
  pull request, once `develop` there holds the release the upgrade ships in. If it moved
  `community`, set it back to the commit of `develop` before the merge.
- `opsmill/infrahub-helm`: only when the charts change. Every final Infrahub and Infrahub
  Enterprise release publishes its chart from `stable`, and so does a chart release cut by hand
  there. So the pull request merges while the Infrahub release it ships in is cut, before it is
  published: merged earlier, it ships with a release that was not tested with it. Leave `version`,
  `appVersion` and `prefectTag` alone: the release process sets them on `stable` just before the
  merge.

If the Infrahub pull request moves to a later release, change the release named in these
descriptions.

## 7. Run the tests that CI does not run

A Neo4j or Prefect upgrade also needs these two runs. Run them, or ask a maintainer to.

- Performance: run the tests of `opsmill/infrahub-private-tests` with the new version and with the
  current one, on the same datasets, and compare the failures and the durations. Check in the
  output of each run that it used the version you meant.
- High availability on Kubernetes: deploy the example of the
  [high-availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx)
  (`development/deploy.tf` deploys the same) and test it by hand. The example pins an old chart
  and image, so install the `infrahub-enterprise` chart from a checkout of `opsmill/infrahub-helm`
  as its `AGENTS.md` describes, with `-f charts/infrahub-enterprise/values.small.yaml` before the
  values file of the example. Set `infrahub.global.infrahubTag` and
  `infrahub.prefect-server.global.prefect.image.prefectTag` to the image you test.

Run both on images built from the upgrade branch. With the user's agreement, add the `cd/preview`
label to the Infrahub pull request for `opsmill/infrahub`, and for `opsmill/infrahub-enterprise` to
a draft pull request in `opsmill/infrahub-private` whose `community` points at the upgrade branch.
Each push then publishes the image with the tag `dev-` followed by the first 7 characters of the
commit. For an image without the upgrade, run the "Publish development docker image" workflow of
the same repository with a commit that does not have it.

## 8. Mark the Infrahub pull request ready

It is ready for review when its CI and the `opsmill/infrahub-private` tests of step 6 pass and,
for Neo4j and Prefect, the two runs of step 7 pass. Once the user agrees, mark it ready.

Never merge any of the pull requests yourself. A maintainer merges the Infrahub pull request and
then the `opsmill/infrahub-private` one. The person who cuts the release merges the
`opsmill/infrahub-helm` one: `/cut-release` has this step.

## Service notes

### Neo4j

- Versions are `YYYY.MM.PATCH`, in the images `neo4j:<version>-community` and
  `neo4j:<version>-enterprise`. The Helm charts drop the leading zero of the month (chart
  `2026.9.0` runs Neo4j `2026.09.0`), and `AGENTS.md` names `Neo4j 2026.09`. Some images can be
  older than the current version, so search for all of them, with the exclusions of step 4:

  ```bash
  git grep -nE 'neo4j:[0-9]{4}\.[0-9]{2}\.[0-9]+'
  git grep -nF -e '<old chart version>' -e 'Neo4j <old YYYY.MM>'
  ```

- Latest versions, then the release notes at <https://neo4j.com/release-notes/> and the upgrade
  guide at <https://neo4j.com/docs/upgrade-migration-guide/current/>:

  ```bash
  curl -s "https://hub.docker.com/v2/repositories/library/neo4j/tags?page_size=100&ordering=last_updated" \
    | jq -r '.results[].name' | grep -E '^[0-9]{4}\.[0-9]{2}\.[0-9]+-enterprise$' | head -5
  ```

- Check the Cypher changes in the output of the component tests, deprecation warnings included.
  Open a data volume of the current version with the new one, and back it up and restore it with
  `utilities/db_backup`. Compare the memory settings of the size presets in the other two
  repositories with the release notes, and check that the `neo4j` driver and `neo4j-rust-ext` in
  `pyproject.toml` support the new version.
- The end-to-end job of `.github/workflows/ci.yml` sets its own Neo4j image: changing it is a CI
  change, which `AGENTS.md` says to agree on first.
- Performance runs: set `NEO4J_DOCKER_IMAGE`, or `DATABASE_DOCKER_IMAGE` for a cluster, in both
  runs, because the defaults of the test containers can differ. The high-availability example
  installs the `neo4j/neo4j` charts itself: install them at the new chart version.

### Prefect

- The `prefect` package in the Infrahub image runs both the Prefect server and the task workers.
  `opsmill/infrahub-private` has no pin: it takes Prefect from `community`.
- Latest versions, then the release notes at <https://github.com/PrefectHQ/prefect/releases>. Read
  every release in the range, because patch releases can contain breaking changes:

  ```bash
  curl -s https://pypi.org/pypi/prefect/json | jq -r '.releases | keys[]' \
    | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -5
  ```

- Find the pins with `git grep -nE 'prefect(-client|-redis)?==|prefecthq/prefect:'`, then run
  `uv lock` in the repository root and in `python_testcontainers/`. Comments and links that name
  the version: `git grep -nF '<current version>' -- ':!*.lock'`, with the exclusions of step 4.
- Check the methods that `backend/infrahub/workers/infrahub_async.py` overrides against
  `src/prefect/workers/base.py` of the new version, and the facts that comments state about the
  current version. Check the task manager migrations on a large task history, the health check
  (`--with-healthcheck`), and the `PREFECT_` settings of each repository
  (`git grep -lE 'PREFECT_|INFRAHUB_TASKMANAGER_'`). List in the pull request the other packages
  that the lock file moves.
- The image is what changes the Prefect version in the test runs: the performance run with the
  current version needs an image without the upgrade. Change the `prefect-server` chart of
  `opsmill/infrahub-helm` only if the new version needs it.

### Redis, RabbitMQ, PostgreSQL and NATS

- RabbitMQ is the message bus, Redis the cache and the locks, and PostgreSQL the database of the
  task manager. NATS replaces RabbitMQ and Redis when `INFRAHUB_USE_NATS=true`.
- Latest versions: the Neo4j query with the image name and tag pattern changed: `redis` (`X.Y.Z`),
  `rabbitmq` (`X.Y.Z-management`), `postgres` (`N-alpine`), `nats` (`X.Y.Z-alpine`). Release notes:
  <https://github.com/redis/redis/releases>, <https://github.com/rabbitmq/rabbitmq-server/releases>,
  <https://www.postgresql.org/docs/release/>, <https://github.com/nats-io/nats-server/releases>.
- Check the adapters in `backend/infrahub/services/adapters/`, the locks in
  `backend/infrahub/lock.py` and `backend/infrahub/locks/`, and the client packages `redis`,
  `aio-pika` and `nats-py`. A new major version of PostgreSQL cannot start on the data of an older
  one: say in the changelog fragment that deployments need a dump and restore or `pg_upgrade`.
- Whether `opsmill/infrahub-helm` changes is not decided: ask a maintainer. Ask too whether to run
  the tests of step 7.

## Report

Tell the user, for each repository, what changed and the link to its pull request, what you
tested, and what is still to do before the merge.
