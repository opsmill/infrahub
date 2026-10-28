# Prefect

Infrahub uses Prefect as its task manager: the `prefect` package in the Infrahub image runs both
the Prefect server and the task workers.

List the latest versions:

```bash
curl -s https://pypi.org/pypi/prefect/json | jq -r '.releases | keys[]' \
  | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -5
```

Release notes: <https://github.com/PrefectHQ/prefect/releases>. Read every release in the range,
because patch releases can contain breaking changes.

## What to check

- The task worker: `backend/infrahub/workers/infrahub_async.py` overrides methods of the Prefect
  worker. Compare them with `src/prefect/workers/base.py` of the new version.
- Comments and links that state a fact about the current Prefect version, for example the note on
  the client connection pool in `backend/infrahub/workers/infrahub_async.py`: check the fact again
  before you change the number.
- The database migrations that the task manager runs on its first start, and how long they take on
  a large task history.
- The Prefect settings that Infrahub sets (the `PREFECT_` variables in `docker-compose.yml`,
  `development/Dockerfile` and the Helm charts): a setting can change its meaning, its default or
  the moment it is read.
- The health check of the task worker (`--with-healthcheck`).
- The other packages that the lock file moves with Prefect: list them in the pull request.

## `opsmill/infrahub`

The first command finds the pins. The second finds the comments and links that name the current
version.

```bash
git grep -nE 'prefect(-client|-redis)?==|prefecthq/prefect:'
git grep -nF '<current version>' -- ':!*.lock' ':!CHANGELOG.md' ':!changelog' \
  ':!docs/docs/release-notes' ':!dev/specs' ':!docs/archive'
```

- `pyproject.toml`: `prefect`, and `prefect-redis` if the new version needs a newer one
- `python_testcontainers/pyproject.toml`: `prefect-client`, at the same version as `prefect`
- `backend/tests/helpers/utils.py`: the image of the Prefect test server. Check that the tag exists:
  `curl -s -o /dev/null -w '%{http_code}' https://hub.docker.com/v2/repositories/prefecthq/prefect/tags/<tag>`
  prints `200`.
- `uv.lock` and `python_testcontainers/uv.lock`: run `uv lock` in the repository root and in
  `python_testcontainers/`

## `opsmill/infrahub-private`

There is no version to change: Prefect comes from the `community` submodule.
`TASK_MANAGER_DOCKER_IMAGE` in `tasks/shared.py` names an old Prefect image that no Docker Compose
file uses, so leave it.

- Compare the Prefect settings with the release notes. Find them with
  `git grep -lE 'PREFECT_|INFRAHUB_TASKMANAGER_'`. They are in `docker-compose.yml`, the size
  presets `docker-compose.<size>.yml`, the files in `development/`, and `development/Dockerfile`,
  which builds the Enterprise image.
- The Enterprise task worker in `enterprise/backend/infrahub_enterprise/workers/` extends the
  Infrahub task worker: check it against the same worker changes.

## `opsmill/infrahub-helm`

- `charts/infrahub/values.yaml`: the task worker environment and the `prefect-server` section
- Every values file of `charts/infrahub-enterprise/`: the size presets run the Prefect web server
  and the background services as separate deployments, with their own batch sizes
- `charts/infrahub/Chart.yaml`: the version of the `prefect-server` dependency, if the new Prefect
  version needs a newer Prefect Helm chart. Then also change its row of the Requirements table in
  `charts/infrahub/README.md` by hand (no CI job runs helm-docs, which generates the table), and
  add a changelog fragment for each chart that changes.
- Leave `prefectTag` alone: the release process sets it to the Infrahub version, and that image
  carries the new Prefect.

## Tests that CI does not run

- Performance: the task manager of the test stack runs the Infrahub image, so the image is what
  changes the Prefect version. The test containers take it from `INFRAHUB_TESTING_DOCKER_IMAGE` and
  `INFRAHUB_TESTING_IMAGE_VERSION`. For the run with the current version, build an image as step 7
  of the skill describes, from the commit of `develop` that the upgrade branch starts from.
- High availability: the Prefect server runs the image that `prefectTag` names, so set it as well
  as `infrahubTag`. Otherwise the Prefect server runs the released Prefect version.
