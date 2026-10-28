# Redis, RabbitMQ, PostgreSQL and NATS

Infrahub uses RabbitMQ as its message bus, Redis as its cache and for its locks, and PostgreSQL as
the database of the task manager. NATS can replace both RabbitMQ and Redis when
`INFRAHUB_USE_NATS=true`.

List the latest versions of an image, here Redis (change the image name and the tag pattern):

```bash
curl -s "https://hub.docker.com/v2/repositories/library/redis/tags?page_size=100&ordering=last_updated" \
  | jq -r '.results[].name' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -5
```

| Service | Tag pattern | Release notes |
|---|---|---|
| Redis | `X.Y.Z` | <https://github.com/redis/redis/releases> |
| RabbitMQ | `X.Y.Z-management` | <https://github.com/rabbitmq/rabbitmq-server/releases>, <https://www.rabbitmq.com/docs/upgrade> |
| PostgreSQL | `N-alpine` | <https://www.postgresql.org/docs/release/> |
| NATS | `X.Y.Z-alpine` | <https://github.com/nats-io/nats-server/releases> |

## What to check

- Redis: the commands that the cache adapter `backend/infrahub/services/adapters/cache/redis.py`
  and the locks in `backend/infrahub/lock.py` and `backend/infrahub/locks/` send.
- RabbitMQ: the message bus adapter `backend/infrahub/services/adapters/message_bus/rabbitmq.py`
  and `backend/infrahub/message_bus/`, and the version of the management plugin, which is part of
  the image tag.
- PostgreSQL: a new major version cannot start on the data directory of an older one, so existing
  deployments need a dump and restore or `pg_upgrade` of the task manager database. Say so in the
  changelog fragment.
- NATS: the JetStream features that `backend/infrahub/services/adapters/cache/nats.py` and
  `backend/infrahub/services/adapters/message_bus/nats.py` use.
- The client package in `pyproject.toml` supports the new server version: `redis` for Redis,
  `aio-pika` for RabbitMQ and `nats-py` for NATS.

## `opsmill/infrahub`

| File | Redis | RabbitMQ | PostgreSQL | NATS |
|---|---|---|---|---|
| `docker-compose.yml` | `CACHE_DOCKER_IMAGE` default | `MESSAGE_QUEUE_DOCKER_IMAGE` default | `POSTGRES_DOCKER_IMAGE` default | |
| `tasks/shared.py` | yes | yes | | both NATS images |
| `development/docker-compose-deps.yml` | yes | yes | yes | |
| `development/docker-compose-deps-nats.yml` | | | yes | |
| `python_testcontainers/infrahub_testcontainers/container.py` | yes | yes | | |
| `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml` | yes | yes | yes | |
| `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml` | yes | yes | yes | |
| `backend/tests/conftest.py` | yes | yes | | |
| `docs/docs/development-resources/local-demo-environment.mdx` | yes | yes | yes | |

Leave the images in `.github/workflows/version-upgrade.yml` unchanged: they are the versions that
the upgrade test starts from.

## `opsmill/infrahub-private`

It pins the same images: Redis, RabbitMQ and PostgreSQL in `docker-compose.yml` and
`development/docker-compose-deps.yml`, Redis, RabbitMQ and NATS in `tasks/shared.py`. Search for
the old tag to find each one.

## `opsmill/infrahub-helm`

Not decided, ask a maintainer. The `infrahub` chart installs Redis and RabbitMQ from Bitnami
charts, PostgreSQL through the `prefect-server` chart and NATS from the `nats` chart, and its Redis
and RabbitMQ versions already differ from the Docker Compose ones. The high-availability example
in this repository uses the same Bitnami charts (`development/deploy.tf`, `development/k8s/`).

## Tests that CI does not run

The private performance tests and the high-availability test are required for Neo4j and Prefect.
For these services, ask a maintainer whether to run them.
