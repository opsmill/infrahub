# Outline: Enterprise install and Community-to-Enterprise migration

Written after drafting, at the user's request to skip the gates. Branch `pcd/docs-enterprise-install`, one pull request.

## Scope

- Enterprise stage 2 on the Miro board: a "Before you start" section on `install/enterprise.mdx`. Smaller update to an existing page.
- Community stage 2b on the Miro board: `install/migrate-to-enterprise.mdx`, already drafted on the branch. Treated as draft source material, revised for voice and causality only.
- Supporting edits: the FAQ answer, the link from the install overview, the Community vs Enterprise migration section, the sidebar entry, and the changelog fragment (all present from earlier work except the FAQ edit).

## Placement

Per the navigation map, Deployment & Management > Install & configure holds installation and the install guides. No new section, no redirects (no published page is renamed or deleted).

## Sources

- Enterprise Compose file served at infrahub.opsmill.io/enterprise: `NEO4J_ACCEPT_LICENSE_AGREEMENT: ${NEO4J_ACCEPT_LICENSE_AGREEMENT:-yes}` (line 296), `INFRAHUB_DOCKER_IMAGE`, `NEO4J_DOCKER_IMAGE`, `VERSION` variables, shared `database_data` volume.
- opsmill.com/legal: lists the End User License Agreement and the Master Services Agreement. It does not say which applies to Enterprise.
- Neo4j Docker documentation: setting `NEO4J_ACCEPT_LICENSE_AGREEMENT=yes` accepts the Enterprise license agreement.
- Neo4j upgrade guide, Community to Enterprise: dump and load of the `neo4j` and `system` databases.
- `overview/community-vs-enterprise.mdx`: the list of Enterprise-only capabilities used in the migration guide's opening.

## Open questions (carried to the pull request)

1. Neo4j data in the migration guide: in-place reuse of the volume or persistent volume claim, or Neo4j's dump and load. Marked with a TODO comment in the page. To be decided after a test.
2. Which OpsMill agreement applies to Enterprise, and who accepts it. The new section says to confirm with OpsMill.
3. Whether the Helm chart also sets the Neo4j acceptance to yes. The board says it does (infrahub-helm values); not verified here, so the new section mentions only the Compose file.
4. Whether pulling `registry.opsmill.io/opsmill/infrahub-enterprise` needs credentials. Neither page says so.
5. `overview/community-vs-enterprise.mdx` still says Enterprise features "can be assessed through trials" and that organizations can "seamlessly migrate". Both conflict with the board and with the revised migration section. Not changed here.
6. The acceptance step proposed on the board (stage 3a) is not shipped, so no page documents it.
