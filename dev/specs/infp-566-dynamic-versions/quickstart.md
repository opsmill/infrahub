# Quickstart: Validating Dynamic Versioning

How to verify the change end-to-end. Commands assume repo root and the repo's pinned
`uv 0.11.6` + `hatch-vcs`.

## 1. Local resolution sanity (FR-005/006/007, US3/US4)

```bash
git fetch --tags                                    # required on a fresh clone (FR-012)

# On a tag → exact version
git checkout infrahub-v1.10.0
uv build --wheel -o /tmp/dv && ls /tmp/dv           # expect infrahub_server-1.10.0-...whl

# Past the tag → dev/local segment, sorts after the tag
git checkout develop
uv build --wheel -o /tmp/dv && ls /tmp/dv           # expect 1.10.1.devN+g<hash>

# testcontainers resolves the SAME version from its subdirectory
( cd python_testcontainers && uv build --wheel -o /tmp/dvtc && ls /tmp/dvtc )
```

## 2. Fallback (US3, no reachable tag)

```bash
git clone --depth 1 file://$PWD /tmp/shallow && cd /tmp/shallow
uv build --wheel -o /tmp/dvfb && ls /tmp/dvfb       # build SUCCEEDS, version ~1.10.1.devN+...
```

## 3. Lockfile churn check (US2/OQ-2)

```bash
uv lock && ( cd python_testcontainers && uv lock )
grep -A2 'name = "infrahub-server"' uv.lock         # expect NO `version =` line
grep -A2 'name = "infrahub-testcontainers"' uv.lock # expect NO `version =` line
# Merge stable↔develop → no version conflict in pyproject.toml / uv.lock
```

## 4. Runtime surfaces (US5 — verification only)

```bash
uv sync
python -c "import importlib.metadata as m; print(m.version('infrahub-server'))"
python -c "from infrahub import __version__; print(__version__)"   # must match the line above
# Then: GET /api/info, GraphQL InfrahubInfo, worker labels, log headers all agree.
```

## 5. Docker image version (FR-020)

```bash
docker buildx build -f development/Dockerfile -t infrahub:dvtest .
docker run --rm infrahub:dvtest python -c \
  "import importlib.metadata as m; print(m.version('infrahub-server'))"   # NOT the fallback
docker run --rm infrahub:dvtest sh -c '[ ! -e /source/.git ] && echo "no .git in image OK"'
docker image inspect infrahub:dvtest --format '{{.Size}}'   # compare to pre-change baseline
```

## 6. Release tasks (US6/FR-017/FR-022)

```bash
uv sync
uv run invoke release.update-helm-chart      # appVersion/version/prefectTag + enterprise dep
uv run invoke release.update-docker-compose  # image tags; never downgrades (strict >)
git diff helm/ docker-compose.yml            # values match installed metadata version
```

## 7. `/cut-release` (FR-021)

Dry-run the rewritten flow in a scratch branch: confirm it determines the version from the
tag, runs towncrier, creates `infrahub-v<new>`, and edits **no** `pyproject.toml`.

## 8. Publish guards (FR-018) — should FAIL loudly

- Simulate a fallback resolution (no tags fetched) on the publish path → publish job MUST fail
  (guard a).
- Simulate resolved ≠ pushed tag segment → publish job MUST fail (guard b).

## Definition of done (maps to Success Criteria)

- [ ] No `[project].version` in either `pyproject.toml`; both lockfiles regenerated (SC-002).
- [ ] All resolver-running checkouts fetch tags (SC-003).
- [ ] All `uv version --short` sites migrated; release.yml guards in place (SC-004).
- [ ] First release propagates Helm `appVersion` + docker-compose tags with no manual step (SC-006).
- [ ] Docker image reports real version; image size not regressed (SC-004/FR-020).
- [ ] Changelog fragment added; `/pre-ci` clean; `docs.validate` clean.
