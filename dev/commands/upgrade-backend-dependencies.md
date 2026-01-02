````markdown
---
description: Upgrade backend infrastructure dependencies (Neo4j, Redis, RabbitMQ, PostgreSQL, NATS, Memgraph) and create a GitHub PR
allowed-tools: mcp__github__*, Bash(curl:*), Bash(gh:*), Read, Edit, Grep, Glob, WebFetch
argument-hint: [component] (e.g., "neo4j", "redis", "rabbitmq", "postgres", "nats", "memgraph", or "all")
---

# Upgrade Backend Dependencies

This command upgrades backend infrastructure dependencies and creates a GitHub PR.

**Requires**: GitHub MCP server must be available for PR creation and CI monitoring.

## Component Argument

The `$ARGUMENTS` can be:
- `neo4j` - Upgrade Neo4j only
- `redis` - Upgrade Redis only
- `rabbitmq` - Upgrade RabbitMQ only
- `postgres` - Upgrade PostgreSQL only
- `nats` - Upgrade NATS only (alternative message broker/cache)
- `memgraph` - Upgrade Memgraph only (alternative graph database)
- `all` - Upgrade all primary components (neo4j, redis, rabbitmq, postgres)

Multiple components can be specified separated by spaces (e.g., `neo4j redis`).

## Step 1: Determine Components to Upgrade

Parse `$ARGUMENTS` to determine which components to upgrade.

**If no argument is provided or `$ARGUMENTS` is empty:**
1. Present the user with the list of available components and their current versions
2. Ask the user to explicitly select which component(s) they want to upgrade
3. Wait for user confirmation before proceeding

**Do NOT default to upgrading all components.** Always require explicit user selection.

Components and their current version locations:

### Neo4j
Current versions defined in:
- `backend/tests/helpers/constants.py` - `NEO4J_COMMUNITY_IMAGE`, `NEO4J_ENTERPRISE_IMAGE`
- `docker-compose.yml` - `NEO4J_DOCKER_IMAGE` default
- `tasks/shared.py` - `NEO4J_DOCKER_IMAGE`
- `python_testcontainers/infrahub_testcontainers/container.py`
- `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`
- `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`
- `utilities/db_backup/__main__.py` - `NEO4J_BACKUP_DOCKER_IMAGE`
- `.github/workflows/version-upgrade.yml`
- `docs/docs/topics/local-demo-environment.mdx`
- `docs/docs/guides/installation.mdx` - Helm chart versions

### Redis
Current versions defined in:
- `docker-compose.yml` - `CACHE_DOCKER_IMAGE` default
- `development/docker-compose-deps.yml`
- `tasks/shared.py` - cache image
- `python_testcontainers/infrahub_testcontainers/container.py`
- `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`
- `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`
- `backend/tests/conftest.py`
- `docs/docs/topics/local-demo-environment.mdx`
- `docs/docs/guides/installation.mdx` - Helm chart versions

### RabbitMQ
Current versions defined in:
- `docker-compose.yml` - `MESSAGE_QUEUE_DOCKER_IMAGE` default
- `development/docker-compose-deps.yml`
- `tasks/shared.py` - message queue image
- `python_testcontainers/infrahub_testcontainers/container.py`
- `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`
- `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`
- `backend/tests/conftest.py`
- `docs/docs/topics/local-demo-environment.mdx`
- `docs/docs/guides/installation.mdx` - Helm chart versions

### PostgreSQL
Current versions defined in:
- `docker-compose.yml` - `POSTGRES_DOCKER_IMAGE` default
- `development/docker-compose-deps.yml`
- `development/docker-compose-deps-nats.yml`
- `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`
- `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`
- `docs/docs/topics/local-demo-environment.mdx`

### NATS (Alternative to RabbitMQ/Redis)
Current versions defined in:
- `tasks/shared.py` - NATS image versions (used when `INFRAHUB_USE_NATS=true`)
- `development/docker-compose-deps-nats.yml`

### Memgraph (Alternative to Neo4j)
Current versions defined in:
- `tasks/shared.py` - `MEMGRAPH_DOCKER_IMAGE`
- `development/docker-compose-database-memgraph.yml`

## Step 2: Fetch Latest Versions

For each component being upgraded, fetch the latest stable version:

### Neo4j
Use the Docker Hub API or Neo4j release page:
```bash
curl -s "https://hub.docker.com/v2/repositories/library/neo4j/tags?page_size=100&ordering=last_updated" | jq -r '.results[].name' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+-enterprise$' | head -5
```

Or check: https://neo4j.com/docs/operations-manual/current/installation/

**Note**: Neo4j uses a `YYYY.MM.PATCH` versioning scheme (e.g., `2025.03.0`). Both `-community` and `-enterprise` variants need to be updated.

### Redis
```bash
curl -s "https://hub.docker.com/v2/repositories/library/redis/tags?page_size=100&ordering=last_updated" | jq -r '.results[].name' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -5
```

### RabbitMQ
```bash
curl -s "https://hub.docker.com/v2/repositories/library/rabbitmq/tags?page_size=100&ordering=last_updated" | jq -r '.results[].name' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+-management$' | head -5
```

### PostgreSQL
```bash
curl -s "https://hub.docker.com/v2/repositories/library/postgres/tags?page_size=100&ordering=last_updated" | jq -r '.results[].name' | grep -E '^[0-9]+-alpine$' | head -5
```

### NATS (if upgrading)
```bash
curl -s "https://hub.docker.com/v2/repositories/library/nats/tags?page_size=100&ordering=last_updated" | jq -r '.results[].name' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+-alpine$' | head -5
```

### Memgraph (if upgrading)
```bash
curl -s "https://hub.docker.com/v2/repositories/memgraph/memgraph-mage/tags?page_size=100&ordering=last_updated" | jq -r '.results[].name' | grep -E 'memgraph-[0-9]+\.[0-9]+-no-ml$' | head -5
```

## Step 3: Fetch and Analyze Release Notes

For each component being upgraded, fetch the release notes and migration guides to identify potential breaking changes and required code modifications.

### Release Notes URLs

- **Neo4j**: https://neo4j.com/release-notes/ and https://neo4j.com/docs/upgrade-migration-guide/current/
- **Redis**: https://github.com/redis/redis/releases and https://raw.githubusercontent.com/redis/redis/refs/heads/{version}/00-RELEASENOTES
- **RabbitMQ**: https://github.com/rabbitmq/rabbitmq-server/releases and https://www.rabbitmq.com/docs/upgrade
- **PostgreSQL**: https://www.postgresql.org/docs/release/ and https://www.postgresql.org/docs/{version}/release.html
- **NATS**: https://github.com/nats-io/nats-server/releases
- **Memgraph**: https://github.com/memgraph/memgraph/releases and https://memgraph.com/docs/release-notes

### Analysis Process

For each component upgrade:

1. **Fetch release notes** for all versions between current and target version
2. **Identify breaking changes** by searching for:
   - "BREAKING" or "Breaking change"
   - "Deprecated" or "Removed"
   - "Migration required"
   - Configuration changes
   - API changes
3. **Search the codebase** for potentially affected code:
   - Use `grep_search` to find usages of deprecated features
   - Check configuration files for deprecated options
   - Verify driver/client library compatibility

### Codebase Impact Analysis

Perform a targeted search of the codebase for each component:

#### Neo4j Analysis
Search for:
- Cypher queries: `grep -r "MATCH\|MERGE\|CREATE\|DELETE" backend/`
- Neo4j driver usage: `grep -r "neo4j\." backend/`
- Configuration: Check `NEO4J_` environment variables and connection settings

#### Redis Analysis
Search for:
- Redis commands: `grep -r "redis\." backend/`
- Cache operations: Search for cache-related code in `backend/infrahub/cache/`
- Configuration: Check `CACHE_` environment variables

#### RabbitMQ Analysis
Search for:
- AMQP operations: `grep -r "aio_pika\|pika\|amqp" backend/`
- Message queue code: Search in `backend/infrahub/message_bus/`
- Configuration: Check `MESSAGE_QUEUE_` environment variables

#### PostgreSQL Analysis
Search for:
- SQL queries: `grep -r "SELECT\|INSERT\|UPDATE\|DELETE" backend/`
- SQLAlchemy usage: `grep -r "sqlalchemy" backend/`
- Configuration: Check `POSTGRES_` environment variables

#### NATS Analysis
Search for:
- NATS client usage: `grep -r "nats\." backend/`
- JetStream operations: Search for JetStream-related code
- Configuration: Check NATS configuration files

#### Memgraph Analysis
Search for:
- Cypher queries (may differ from Neo4j): Check compatibility
- MAGE procedures: Search for `CALL` statements with Memgraph-specific procedures
- Configuration: Check Memgraph-specific settings

### Generate Upgrade Recommendations

Based on the release notes analysis and codebase search, generate a report:

```markdown
## Upgrade Impact Analysis: {Component} {current_version} → {target_version}

### Breaking Changes Identified
- [ ] {breaking_change_1}: Description and affected code locations
- [ ] {breaking_change_2}: Description and affected code locations

### Deprecated Features in Use
- [ ] {deprecated_feature}: Found in {file_paths}, recommended replacement: {replacement}

### Required Code Changes
1. {change_1}: {description}
   - Files affected: {file_list}
   - Recommended fix: {fix_description}

### Configuration Changes Required
- [ ] {config_change}: {old_value} → {new_value}

### Driver/Library Compatibility
- Current driver version: {current}
- Required driver version: {required}
- Update command: `uv add {package}=={version}`

### Risk Assessment
- **Risk Level**: Low/Medium/High
- **Reason**: {explanation}

### Recommended Actions Before Upgrade
1. {action_1}
2. {action_2}
```

**Wait for user review of the impact analysis before proceeding with the upgrade.**

## Step 4: Present Version Comparison to User

Create a comparison table showing:
- Component name
- Current version
- Latest available version
- Whether an upgrade is recommended
- Summary of breaking changes (from Step 3 analysis)

Ask the user to confirm:
1. Which components to upgrade
2. Target versions for each component (can differ from latest)
3. Whether they have reviewed and accepted the upgrade recommendations
4. Whether to proceed with the upgrade

**Wait for explicit user confirmation before proceeding.**

## Step 5: Create a Feature Branch

Using the GitHub MCP server, create a new branch:
```
Branch name: deps/upgrade-{component}-{version}
Example: deps/upgrade-neo4j-2025.04.0
Example for all: deps/upgrade-backend-deps-{date}
```

Use `gh` CLI or MCP to create and checkout the branch:
```bash
git checkout -b deps/upgrade-backend-deps-$(date +%Y%m%d)
```

## Step 6: Update Version Files

For each component being upgraded, update ALL relevant files:

### Neo4j Updates
1. `backend/tests/helpers/constants.py`:
   - Update `NEO4J_COMMUNITY_IMAGE`
   - Update `NEO4J_ENTERPRISE_IMAGE`

2. `docker-compose.yml`:
   - Update `NEO4J_DOCKER_IMAGE` default value

3. `tasks/shared.py`:
   - Update `NEO4J_DOCKER_IMAGE` default

4. `python_testcontainers/infrahub_testcontainers/container.py`:
   - Update `NEO4J_DOCKER_IMAGE` in env dict

5. `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`:
   - Update `NEO4J_DOCKER_IMAGE` default

6. `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`:
   - Update `DATABASE_DOCKER_IMAGE` defaults (multiple services)

7. `utilities/db_backup/__main__.py`:
   - Update `NEO4J_BACKUP_DOCKER_IMAGE` default

8. `.github/workflows/version-upgrade.yml`:
   - Update `neo4j_image` in matrix

9. `docs/docs/topics/local-demo-environment.mdx`:
   - Update the Neo4j version in the components table

10. `docs/docs/guides/installation.mdx`:
    - Update Helm chart versions for Neo4j

### Redis Updates
1. `docker-compose.yml`:
   - Update `CACHE_DOCKER_IMAGE` default

2. `development/docker-compose-deps.yml`:
   - Update `CACHE_DOCKER_IMAGE` default

3. `tasks/shared.py`:
   - Update Redis image version

4. `python_testcontainers/infrahub_testcontainers/container.py`:
   - Update `CACHE_DOCKER_IMAGE`

5. `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`:
   - Update `CACHE_DOCKER_IMAGE` default

6. `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`:
   - Update `CACHE_DOCKER_IMAGE` default

7. `backend/tests/conftest.py`:
   - Update Redis DockerContainer image

8. `docs/docs/topics/local-demo-environment.mdx`:
   - Update Redis version in components table

9. `docs/docs/guides/installation.mdx`:
   - Update Helm chart version for Redis

### RabbitMQ Updates
1. `docker-compose.yml`:
   - Update `MESSAGE_QUEUE_DOCKER_IMAGE` default

2. `development/docker-compose-deps.yml`:
   - Update `MESSAGE_QUEUE_DOCKER_IMAGE` default

3. `tasks/shared.py`:
   - Update RabbitMQ image version

4. `python_testcontainers/infrahub_testcontainers/container.py`:
   - Update `MESSAGE_QUEUE_DOCKER_IMAGE`

5. `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`:
   - Update `MESSAGE_QUEUE_DOCKER_IMAGE` default

6. `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`:
   - Update `MESSAGE_QUEUE_DOCKER_IMAGE` default

7. `backend/tests/conftest.py`:
   - Update RabbitMQ DockerContainer image

8. `docs/docs/topics/local-demo-environment.mdx`:
   - Update RabbitMQ version in components table

9. `docs/docs/guides/installation.mdx`:
   - Update Helm chart version for RabbitMQ

### PostgreSQL Updates
1. `docker-compose.yml`:
   - Update `POSTGRES_DOCKER_IMAGE` default

2. `development/docker-compose-deps.yml`:
   - Update postgres image

3. `development/docker-compose-deps-nats.yml`:
   - Update postgres image

4. `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml`:
   - Update `POSTGRES_DOCKER_IMAGE` default

5. `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`:
   - Update `POSTGRES_DOCKER_IMAGE` default

6. `docs/docs/topics/local-demo-environment.mdx`:
   - Update PostgreSQL version in components table

### NATS Updates (if upgrading)
1. `tasks/shared.py`:
   - Update NATS image version in `MESSAGE_QUEUE_DOCKER_IMAGE` conditional
   - Update NATS image version in `CACHE_DOCKER_IMAGE` conditional

2. `development/docker-compose-deps-nats.yml`:
   - Update NATS image versions

### Memgraph Updates (if upgrading)
1. `tasks/shared.py`:
   - Update `MEMGRAPH_DOCKER_IMAGE`

2. `development/docker-compose-database-memgraph.yml`:
   - Update Memgraph image version

## Step 7: Apply Required Code Changes

Based on the analysis from Step 3, apply any required code changes identified in the upgrade recommendations:

1. **Update deprecated code patterns** to use recommended replacements
2. **Modify configuration files** if format changes are required
3. **Update driver/client libraries** if version bumps are needed:
   ```bash
   uv add {package}=={version}
   ```
4. **Update query syntax** if breaking changes affect Cypher/SQL queries

Document all code changes made beyond version bumps in the PR description.

## Step 8: Create Changelog Entry

Create a changelog entry using towncrier:

```bash
uv run towncrier create +upgrade-{component}.changed.md -c "Upgraded {component} from {old_version} to {new_version}"
```

Or for multiple components:
```bash
uv run towncrier create +upgrade-deps-$(date +%Y%m%d).changed.md -c "Upgraded backend dependencies: Neo4j to X.Y.Z, Redis to X.Y.Z, RabbitMQ to X.Y.Z, PostgreSQL to X"
```

## Step 9: Validate Changes Locally

Before creating the PR, run local validation:

```bash
# Format code
uv run invoke format

# Lint code
uv run invoke lint

# Validate docs (if docs were updated)
uv run invoke docs.lint
```

If any validation fails, fix the issues before proceeding.

## Step 10: Commit Changes

```bash
git add -A
git commit -m "chore(deps): upgrade {component(s)} to {version(s)}

- Updated {component} from {old} to {new}
- Updated all relevant configuration files
- Updated documentation
- Applied required code changes per migration guide"
```

## Step 11: Push Branch and Create PR

Using the GitHub MCP server:

1. Push the branch:
   ```bash
   git push -u origin {branch-name}
   ```

2. Create a PR using MCP `mcp__github__create_pull_request`:
   - Title: `chore(deps): Upgrade {component(s)} to {version(s)}`
   - Body: Include:
     - Summary of changes
     - Version comparison table
     - Links to release notes for each component
     - Breaking changes summary from Step 3 analysis
     - Code changes made beyond version bumps
     - Checklist of files updated
   - Base: `develop`
   - Head: `{branch-name}`

Example PR body:
```markdown
## Summary
This PR upgrades backend infrastructure dependencies.

## Version Changes
| Component | Previous | New |
|-----------|----------|-----|
| Neo4j | 2025.03.0 | 2025.04.0 |
| Redis | 7.2.11 | 7.4.0 |
| RabbitMQ | 3.13.7 | 3.14.0 |
| PostgreSQL | 16 | 17 |

## Breaking Changes & Migration Notes
<!-- Include relevant breaking changes identified in Step 3 -->
- {breaking_change_1}: How it was addressed
- {breaking_change_2}: How it was addressed

## Code Changes Beyond Version Bumps
<!-- List any code changes made to accommodate the upgrade -->
- {file_path}: {description of change}

## Release Notes
- [Neo4j Release Notes](https://neo4j.com/release-notes/)
- [Redis Release Notes](https://github.com/redis/redis/releases)
- [RabbitMQ Release Notes](https://github.com/rabbitmq/rabbitmq-server/releases)
- [PostgreSQL Release Notes](https://www.postgresql.org/docs/release/)

## Files Updated
- [ ] `backend/tests/helpers/constants.py`
- [ ] `docker-compose.yml`
- [ ] `tasks/shared.py`
- [ ] Test container configurations
- [ ] Documentation
- [ ] Changelog entry

## Testing
- [ ] CI passes all tests
- [ ] Local docker-compose starts successfully
- [ ] Integration tests pass
- [ ] No performance regression when running infrahub-private-tests (scale tests)
- [ ] Migration and auto-upgrade of persistent containers pass (version-upgrade job succeeds)
- [ ] Helm chart has been tested with upgraded dependencies
```

## Step 12: Monitor CI and Report Results

After PR creation:

1. Use MCP `mcp__github__get_pull_request` to get the PR number
2. Wait for CI checks to start (poll every 30 seconds initially)
3. Use MCP `mcp__github__list_pull_request_commits` and check status
4. Monitor CI status using:
   - MCP to check PR status/checks
   - `gh pr checks {pr-number}` to see check status

Report to user:
- When CI starts
- Any failing checks with error summaries
- When all checks pass

If CI fails:
1. Fetch the failing check logs
2. Present a summary of errors to the user
3. Ask if they want to investigate/fix the issues
4. If yes, provide guidance on common issues:
   - Version compatibility issues
   - Configuration syntax changes
   - Breaking API changes

## Common Issues and Solutions

### Neo4j
- **Cypher syntax changes**: Check Neo4j release notes for deprecated syntax
- **Driver compatibility**: Ensure `neo4j` Python package supports the new version
- **Authentication changes**: Neo4j 5.x changed default auth mechanisms

### Redis
- **Command deprecations**: Some commands may be deprecated in newer versions
- **Configuration changes**: Check for config file format changes

### RabbitMQ
- **Plugin compatibility**: Management plugin version must match
- **Protocol changes**: AMQP protocol version considerations

### PostgreSQL
- **Schema compatibility**: Major version upgrades may require migrations
- **Extension compatibility**: Check if extensions are available in new version

### NATS
- **JetStream changes**: NATS JetStream API may change between versions
- **Configuration format**: Check for changes in nats-server.conf format
- **Client library compatibility**: Ensure nats.py package supports the new version

### Memgraph
- **Cypher compatibility**: Memgraph may have different Cypher support than Neo4j
- **MAGE module compatibility**: Ensure MAGE modules are compatible with new Memgraph version
- **Query performance**: Some query optimizations may change between versions

## Rollback Instructions

If the upgrade causes issues:

1. Close the PR without merging
2. Delete the branch:
   ```bash
   git branch -D {branch-name}
   git push origin --delete {branch-name}
   ```
3. Document the issues encountered for future reference
````
