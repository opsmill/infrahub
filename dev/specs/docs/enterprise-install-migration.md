# Outline: Enterprise install and Community-to-Enterprise migration

Written after drafting, at the user's request to skip the gates. Branch `pcd/docs-enterprise-install`, one pull request.

## Scope

- Enterprise stage 2 on the Miro board: a "Before you start" section on `install/enterprise.mdx`. Smaller update to an existing page.
- Community stage 2b on the Miro board: the migration guide at `maintain-upgrade/upgrade/community-to-enterprise.mdx`. It comes from the `docs/community-to-enterprise-migration` branch, which had been through a fact-check review. The earlier draft at `install/migrate-to-enterprise.mdx` is removed; its Docker Compose to Kubernetes section is kept in the new page.
- Supporting edits: the FAQ answer, the link from the install overview, the Community vs Enterprise migration section, the sidebar entry, and the changelog fragment (all present from earlier work except the FAQ edit).

## Placement

The migration guide sits in Deployment & Management > Maintain & upgrade > Upgrade, next to the Community and Enterprise upgrade guides, because the procedure ends with `infrahub upgrade` and has a rollback section. The install pages link to it. No new section, no redirects (the earlier draft was never published).

## Sources

- Enterprise Compose file served at infrahub.opsmill.io/enterprise: `NEO4J_ACCEPT_LICENSE_AGREEMENT: ${NEO4J_ACCEPT_LICENSE_AGREEMENT:-yes}` (line 296; the author of the guide states the default is `no`, so the person must set it to `yes`), `INFRAHUB_DOCKER_IMAGE`, `NEO4J_DOCKER_IMAGE`, `VERSION` variables, shared `database_data` volume.
- opsmill.com/legal: lists the End User License Agreement and the Master Services Agreement. It does not say which applies to Enterprise.
- Neo4j Docker documentation: setting `NEO4J_ACCEPT_LICENSE_AGREEMENT=yes` accepts the Enterprise license agreement.
- Neo4j upgrade guide, Community to Enterprise: dump and load of the `neo4j` and `system` databases.
- `overview/community-vs-enterprise.mdx`: the list of Enterprise-only capabilities used in the migration guide's opening.
- The author of the page (2026-11-11): Infrahub Enterprise requires the person to accept the Infrahub license agreement with `INFRAHUB_ACCEPT_LICENSE_AGREEMENT`. The backend team is implementing the check; the Compose file and the Helm chart were not checked.
- infrahub-helm `charts/infrahub/values.yaml` (`stable`): the API server and the task workers each take an `env` map, under `infrahubServer.infrahubServer.env` and `infrahubTaskWorker.infrahubTaskWorker.env`.

## Open questions (carried to the pull request)

1. Neo4j data in the migration guide: the page reuses the volume or persistent volume claim and covers the block store format conversion. It has not been tested here against the dump and load route in the Neo4j upgrade guide.
2. Which OpsMill agreement applies to Enterprise, and who accepts it. The new section says to confirm with OpsMill.
3. Whether the Helm chart also sets the Neo4j acceptance to yes. The board says it does (infrahub-helm values); not verified here, so the new section mentions only the Compose file.
4. Whether pulling `registry.opsmill.io/opsmill/infrahub-enterprise` needs credentials. Neither page says so.
5. `overview/community-vs-enterprise.mdx` still says Enterprise features "can be assessed through trials" and that organizations can "seamlessly migrate". Both conflict with the board and with the revised migration section. Not changed here.
6. `install/enterprise.mdx` now documents `INFRAHUB_ACCEPT_LICENSE_AGREEMENT` before the backend check ships. Not known yet: the accepted value (the page uses `yes`, like the Neo4j variable), which Infrahub components read it (the page sets it on the API server and the task workers), and what happens when it is missing. The migration guide also documents it, with the same assumptions, and its Docker Compose pre-flight check assumes the Enterprise Compose file sets it on the `infrahub-server` and `task-worker` services.
