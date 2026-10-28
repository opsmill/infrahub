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

## 1. Agree on the scope and the release

Ask the user which services to upgrade and to which version. Never default to all of them. The
reference file has a query that lists the latest versions.

Then find the Infrahub release that the upgrade ships in, and confirm it with the user. It is the
release that `develop` holds: the minor release after the latest release tag
(`git ls-remote --tags origin 'infrahub-v*'`), or the one after that when a `release-x.y` branch
already holds that next minor release. For example, with `infrahub-v1.11.9` as the latest tag and
a `release-1.12` branch, the upgrade ships in 1.13.0. Infrahub Enterprise releases use the same
version numbers.

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
to find any pin the list misses. Use the search of the reference file when it has one, because it
also finds the other forms of the version. Otherwise search for the old tag:

```bash
git grep -nF '<old tag>' -- ':!CHANGELOG.md' ':!changelog' ':!docs/docs/release-notes' \
  ':!dev/specs' ':!docs/archive' ':!.github/workflows/version-upgrade.yml'
```

The search leaves out the files that record past changes, which stay as they are, and
`.github/workflows/version-upgrade.yml`: its images are the versions that the upgrade test starts
from, so they stay as they are too.

Add a changelog fragment of type `changed` with the `creating-changelog-entries` skill, because the
version that users run changes. Before you push, run the checks that `AGENTS.md` lists.

## 5. Open the Infrahub pull request

Open it as a draft against `develop` with the `pr` skill, with the title
`chore(deps): upgrade <service> from <old version> to <new version>`. In the description, write:

- The release it ships in.
- Each change in the release notes that can reach Infrahub, and how you checked it.
- What you did not test, and why.
- The pull requests in the other repositories, each with the release it ships in, or "no change
  needed". Add them once step 6 opens them.
- The results of the tests of steps 6 and 7, or that they are still to do.

## 6. Change the other two repositories

Read the `AGENTS.md` of each repository before you change it. Change every file that the reference
lists for it, and search there for the old version too. Show the user the changes for each
repository, and open the pull requests only after they agree. Open each one as a draft that links
the Infrahub pull request and names the release the upgrade ships in. It must ship in that
release, not in an earlier one that was not tested with it.

- `opsmill/infrahub-private`: its tests must pass with the new version too, so open a pull request
  there for every upgrade, also when no file has to change there. Point its `community` submodule
  at the last commit of the Infrahub upgrade branch, and again after each push to that branch. Its
  CI then runs the Enterprise unit, component, functional, Docker integration and end-to-end tests
  on the new version. Its `AGENTS.md` says how to run the same tests on your machine, for example
  to debug a failure.
  - If a test fails, check whether it also fails without the upgrade: open a second draft pull
    request from `develop` there that only points `community` at the commit of `develop` that the
    upgrade branch starts from. A test that fails in both does not fail because of the upgrade, but
    because the Enterprise code does not support `develop` of `opsmill/infrahub` yet: say so in the
    Infrahub pull request. Close the second pull request once you no longer need it.
  - The pull request merges after the Infrahub pull request, once `develop` there holds the release
    the upgrade ships in. While `opsmill/infrahub` has a `release-x.y` branch that
    `opsmill/infrahub-private` does not have, `develop` there still holds release x.y.
  - `community` on `develop` there points at Infrahub release tags. So before the merge, update the
    pull request from `develop` and keep the `community` commit of `develop`. When no other change
    is left, close the pull request instead of merging it.
- `opsmill/infrahub-helm`: when the reference says that nothing has to change there, open no pull
  request and write "no change needed" in the Infrahub pull request. Every final Infrahub and
  Infrahub Enterprise release publishes its chart from `stable`, and so does a chart release cut
  by hand there. So the pull request merges while that Infrahub release is cut, before it is
  published, and only if the Infrahub pull request is part of that release. Merged earlier, it
  ships with a release that was not tested with it. Merged later, the charts of the release do not
  contain it. Leave `version` and `appVersion` alone: the release process changes them on `stable`
  just before the merge, so a change in the pull request conflicts with it.

If the Infrahub pull request moves to a later release, change the release named in these
descriptions.

## 7. Run the tests that CI does not run

A Neo4j or Prefect upgrade also needs these two runs. Run them, or ask a maintainer to. The
reference file says what each run needs for its service.

- Performance: run the tests of `opsmill/infrahub-private-tests` with the new version and with the
  current one, on the same datasets, and compare the failures and the durations. Check in the
  output of each run that it used the version you meant to test.
- High availability on Kubernetes: no CI job deploys this setup. It runs a Neo4j cluster and splits
  the Prefect server into a web server and background services. Deploy the example from the
  [high-availability guide](../../../docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx),
  which `development/deploy.tf` also deploys, and test it by hand. The example pins a published
  chart and an Infrahub image that can be much older than the code you test, so change two things:
  - Install the `infrahub-enterprise` chart from a checkout of `opsmill/infrahub-helm`, as its
    `AGENTS.md` describes, and add `-f charts/infrahub-enterprise/values.small.yaml` before the
    values file of the example. Use the branch of the pull request there, or `stable` when the
    upgrade has none.
  - Set `infrahub.global.infrahubTag` and `infrahub.prefect-server.global.prefect.image.prefectTag`
    to the image you test.

Run both on images built from the upgrade branch, so that they test the code that ships with the
upgrade. Ask the user before you build one, because it publishes an image. Add the `cd/preview`
label to a pull request, and each push to it then publishes an image with the tag `dev-` followed
by the first 7 characters of its last commit:

- `opsmill/infrahub`: on the Infrahub pull request.
- `opsmill/infrahub-enterprise`, which the `infrahub-enterprise` chart needs: on the
  `opsmill/infrahub-private` pull request, whose `community` submodule points at the upgrade.

For a run without the upgrade, build the image with the "Publish development docker image" workflow
of the same repository instead, from the commit of `develop` that the upgrade branch starts from.
For Infrahub Enterprise, give it a commit of `opsmill/infrahub-private` whose `community` points at
that commit, such as the last commit of the second pull request of step 6:

```bash
gh workflow run publish-dev-docker-image.yml --repo <repository> -f commit=<commit>
```

## 8. Mark the Infrahub pull request ready

The upgrade is ready for review when CI passes on the Infrahub pull request and on the
`opsmill/infrahub-private` one and, for Neo4j and Prefect, the two runs of step 7 pass. Post the
results on the Infrahub pull request, and once the user agrees, mark it ready for review.

## Who merges the pull requests

Never merge any of the pull requests yourself. A maintainer merges the Infrahub pull request after
review, and the `opsmill/infrahub-private` one after it. The person who cuts the release merges the
`opsmill/infrahub-helm` one: the `/cut-release` command has this step.

## Report

Tell the user, for each repository, what changed and the link to its pull request, what you
tested, and what is still to do before the merge.
