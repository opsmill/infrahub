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

The versions of the services that an Infrahub deployment runs are pinned in three repositories, so
one upgrade can need a pull request in each:

- `opsmill/infrahub` (this repository): the Docker Compose stack, the test containers, the tests,
  the docs and the Python packages.
- `opsmill/infrahub-private`: Infrahub Enterprise. It pins the same images and sets its own Prefect
  and Neo4j settings.
- `opsmill/infrahub-helm`: the Helm charts that deploy Infrahub on Kubernetes. It pins the Neo4j
  and Prefect server charts and sets the Prefect settings of these deployments.

For each service, a reference file lists every file to change in each repository and what to
check in the release notes. Load only the one for the service you upgrade:

- Neo4j: [references/neo4j.md](references/neo4j.md)
- Prefect: [references/prefect.md](references/prefect.md)
- Redis, RabbitMQ, PostgreSQL and NATS:
  [references/redis-rabbitmq-postgresql-nats.md](references/redis-rabbitmq-postgresql-nats.md)

## 1. Agree on the scope

Ask the user which services to upgrade and to which version. Never default to all of them. The
reference file has a query that lists the latest versions.

## 2. Check what the new version changes

Read the release notes of every version between the current one and the target, not only the
target: breaking changes often sit in the versions in between. For each change that can reach
Infrahub, find the code or setting it touches (the reference file says where to look) and decide
how to check it. Show the user a short report (the breaking changes, the deprecated features that
Infrahub uses, the code or setting changes needed, whether the client library supports the new
version, and the risk) with the files you will change in each repository. Wait for their go before
you change anything.

## 3. Branch from the right base

- `opsmill/infrahub` and `opsmill/infrahub-private`: branch from `develop`. Neo4j and Prefect
  upgrades ship in a feature release and never in a patch release, also for a patch version of
  either, because CI does not run the tests they need and Prefect patch releases can contain
  breaking changes.
- `opsmill/infrahub-helm`: branch from `stable`, its only main branch.

## 4. Change the files in this repository

Change every file that the reference lists for `opsmill/infrahub`. Then search for the old version
to find any pin the list misses:

```bash
git grep -n '<old tag>' -- ':!docs/archive' ':!.github/workflows/version-upgrade.yml'
```

The search leaves out `.github/workflows/version-upgrade.yml` on purpose: its images are the
versions that the upgrade test starts from, so they stay as they are.

Add a changelog fragment of type `changed` with the `creating-changelog-entries` skill, because the
version that users run changes. Before you push, run the checks that `AGENTS.md` lists.

## 5. Change the other two repositories

Read the `AGENTS.md` of each repository before you change it. Change every file that the reference
lists for it, and search there for the old version too. When the reference says that nothing has
to change in a repository, open no pull request there and say so in the Infrahub pull request.

Show the user the changes for each repository, and open the pull requests only after they agree.
Open each one as a draft, and name in its description the Infrahub release the upgrade ships in.
It must ship in that release, not in an earlier one that was not tested with it:

- `opsmill/infrahub-helm`: every final Infrahub and Infrahub Enterprise release publishes its chart
  from `stable`. So the pull request merges while that Infrahub release is cut, before it is
  published, and only if the Infrahub pull request is part of that release. Merged earlier, it
  ships with a release that was not tested with it. Merged later, the charts of the release do not
  contain it. The `/cut-release` command has this step. Leave `version` and `appVersion` alone:
  the release process changes them just before the merge, so a change in the pull request
  conflicts with it.
- `opsmill/infrahub-private`: the pull request merges after the Infrahub pull request, once
  `develop` there holds the release the upgrade ships in. While `opsmill/infrahub` has a
  `release-x.y` branch that `opsmill/infrahub-private` does not have, `develop` there still holds
  release x.y.

If the Infrahub pull request moves to a later release, change the release named in these
descriptions. Never merge any of the pull requests yourself.

## 6. Run the tests that CI does not run

A Neo4j or Prefect upgrade is ready to merge only after these two runs. Run them, or ask a
maintainer to, and post the results on the Infrahub pull request. The reference file says what
each run needs for its service.

- Performance: run the tests of `opsmill/infrahub-private-tests` with the new version and with the
  current one, on the same datasets, and compare the failures and the durations. Check in the
  output of each run that it used the version you meant to test.
- High availability on Kubernetes: deploy the example from the
  [high-availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx),
  which `development/deploy.tf` also deploys, and test it by hand. It runs a Neo4j cluster and
  splits the Prefect server into a web server and background services, and no CI job deploys it.
  Its values pin an older Infrahub image, so set `infrahubTag` and `prefectTag` to the image you
  test.

## 7. Open the Infrahub pull request

Open it against `develop` with the `pr` skill, with the title
`chore(deps): upgrade <service> from <old version> to <new version>`. In the description, write:

- Each change in the release notes that can reach Infrahub, and how you checked it.
- What you did not test, and why.
- The pull requests in the other repositories, each with the release it ships in, or "no change
  needed".
- The results of the two runs, or that they are still to do.

Then watch CI with the `monitoring-pull-requests` skill.

## Report

Tell the user, for each repository, what changed and the link to its pull request, what you
tested, and what is still to do before the merge.
