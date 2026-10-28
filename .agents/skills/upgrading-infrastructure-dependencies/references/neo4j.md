# Neo4j

Neo4j versions are `YYYY.MM.PATCH`, for example `2026.09.0`. The Docker images are
`neo4j:<version>-community` and `neo4j:<version>-enterprise`. The Neo4j Helm charts drop the
leading zero of the month: chart `2026.9.0` runs Neo4j `2026.09.0`.

List the latest versions:

```bash
curl -s "https://hub.docker.com/v2/repositories/library/neo4j/tags?page_size=100&ordering=last_updated" \
  | jq -r '.results[].name' | grep -E '^[0-9]{4}\.[0-9]{2}\.[0-9]+-enterprise$' | head -5
```

Release notes: <https://neo4j.com/release-notes/> and the yearly changelog pages of the
[neo4j/neo4j wiki](https://github.com/neo4j/neo4j/wiki). Upgrade guide:
<https://neo4j.com/docs/upgrade-migration-guide/current/>.

## What to check

- Cypher changes: the component tests of the core, query, branch and GraphQL suites run the queries
  of Infrahub on the new version. Read their output for deprecation warnings too.
- Store format: open a data volume of the current version with the new one, and run a backup and a
  restore with `utilities/db_backup`.
- Memory settings: the size presets of `opsmill/infrahub-helm` set the heap, the page cache and
  the number of parallel runtime workers, and those of `opsmill/infrahub-private` set the heap and
  the page cache. Compare them with what the release notes say about memory.
- The `neo4j` Python driver and `neo4j-rust-ext` in `pyproject.toml` support the new server
  version.

## `opsmill/infrahub`

- `backend/tests/helpers/constants.py`: `NEO4J_COMMUNITY_IMAGE` and `NEO4J_ENTERPRISE_IMAGE`
- `docker-compose.yml`: the `NEO4J_DOCKER_IMAGE` default of the `database` service
- `tasks/shared.py`: `NEO4J_DOCKER_IMAGE`
- `python_testcontainers/infrahub_testcontainers/container.py`: both `NEO4J_DOCKER_IMAGE` values,
  the community default in `PROJECT_ENV_VARIABLES` and the enterprise value in `create_env_file`
- `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`: the `NEO4J_DOCKER_IMAGE`
  default
- `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`: the
  `DATABASE_DOCKER_IMAGE` defaults of the three database services
- `utilities/db_backup/__main__.py`: the `NEO4J_BACKUP_DOCKER_IMAGE` default
- `docs/docs/development-resources/local-demo-environment.mdx`: the components table
- `docs/docs/development/backend.mdx`: the example output of `docker compose ps`
- `docs/docs/deploy-manage/install-configure/production-deployment/high-availability.mdx`: the
  `--version` of the `neo4j/neo4j` and `neo4j/neo4j-headless-service` charts
- `development/deploy.tf`: the versions of the `neo4j` and `neo4j-headless-service` charts
- `AGENTS.md`: the Neo4j version in the Tech Stack line

Leave `neo4j_image` in `.github/workflows/version-upgrade.yml` unchanged: it is the Neo4j version
that the upgrade test starts from. The end-to-end job in `.github/workflows/ci.yml` sets its own
Neo4j image. Changing it is a CI workflow change, which `AGENTS.md` says to agree on first.

## `opsmill/infrahub-private`

- `tasks/shared.py`: `NEO4J_DOCKER_IMAGE`
- `docker-compose.yml`: the Neo4j image of the database service
- `.github/workflows/ci.yml`: `NEO4J_DOCKER_IMAGE`
- The size presets `docker-compose.<size>.yml`: compare their `NEO4J_` settings (heap, page cache)
  with the release notes

## `opsmill/infrahub-helm`

- `charts/infrahub/Chart.yaml`: the version of the `neo4j` dependency
- `charts/infrahub/README.md`: the dependency table
- A changelog fragment in `charts/infrahub/changelog/`
- The `neo4j` section of `charts/infrahub/values.yaml` and of the size presets
  `charts/infrahub-enterprise/values.*.yaml`: compare these settings with the release notes

## Tests that CI does not run

- Performance: the test containers start the Neo4j image of the installed `infrahub-testcontainers`
  release, unless `NEO4J_DOCKER_IMAGE` is set. A cluster deployment reads `DATABASE_DOCKER_IMAGE`
  instead.
- High availability: the example turns off the Neo4j of the Infrahub chart and installs the
  `neo4j/neo4j` chart directly, so use the chart version of the upgrade, from the high-availability
  guide or `development/deploy.tf`.
