import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

// NOTE: External "↗" links below are stubbed with https://TODO-FILL-IN-*.example.com
// URLs. Replace each TODO URL with the real destination before merging this PR.
//
// V3 navigation structure (Phase 2 nav restructure). For unmigrated content,
// sidebar entries point at existing legacy `topics/X` and `guides/X` paths so
// no URLs change. New top-level landing pages and empty sub-categories use
// `generated-index` until real landing/hub pages are authored. NEW pages
// referenced in the recommendation docs (About Objects, Build a generator,
// Write a Jinja2 transformation, etc.) are intentionally omitted from the
// sidebar until the per-feature migration PRs add them.
//
// Top-level "section" entries are non-collapsible categories — gives them
// real menu-link styling without custom CSS.

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'home',

    {
      type: 'category',
      label: 'Get started',
      collapsible: false,
      collapsed: false,
      items: [
        {
          type: 'category',
          label: 'Introduction',
          collapsible: true,
          collapsed: true,
          items: [
            { type: 'doc', id: 'overview/overview', label: 'What is Infrahub?' },
            { type: 'doc', id: 'overview/concepts', label: 'Key Concepts' },
            { type: 'doc', id: 'overview/architecture', label: 'Architecture' },
            { type: 'doc', id: 'overview/community-vs-enterprise', label: 'Community vs Enterprise' },
          ],
        },
        {
          type: 'category',
          label: 'Getting Started',
          collapsible: true,
          collapsed: true,
          items: [
            { type: 'doc', id: 'overview/quickstart', label: 'Quickstart' },
            { type: 'doc', id: 'overview/explore', label: 'Explore Infrahub' },
            { type: 'doc', id: 'overview/next-steps', label: 'Next Steps' },
          ],
        },
        'faq/faq',
      ],
    },

    {
      type: 'category',
      label: 'Learn',
      collapsible: false,
      collapsed: false,
      items: [
        { type: 'doc', id: 'academy/academy', label: 'About Academy' },
        {
          type: 'category',
          label: 'Getting Started',
          link: { type: 'generated-index' },
          items: [
            'academy/getting-started/infrahub-introduction',
            'academy/getting-started/deploy-first-configuration',
          ],
        },
        {
          type: 'category',
          label: 'Tutorials',
          link: { type: 'generated-index' },
          items: [
            'academy/tutorials/build-your-first-schema',
            'academy/tutorials/groups',
            'academy/tutorials/build-a-check',
            'academy/tutorials/transformations/build-a-jinja2-transformation',
            'academy/tutorials/transformations/build-a-python-transformation',
            'academy/tutorials/generators/build-your-first-generator',
            'academy/tutorials/generators/build-chained-generators',
          ],
        },
      ],
    },

    {
      type: 'category',
      label: 'Schema & Data',
      collapsible: false,
      collapsed: false,
      link: { type: 'generated-index', slug: 'schema-and-data' },
      items: [
        // ── About Schema ──────────────────────────────────────
        {
          type: 'category',
          label: 'About Schema',
          link: { type: 'doc', id: 'schema/overview' }, // hub
          items: [
            { type: 'doc', id: 'schema/nodes-and-attributes', label: 'Nodes & attributes' },
            { type: 'doc', id: 'schema/relationships', label: 'Relationships' },
            { type: 'doc', id: 'schema/generics-and-inheritance', label: 'Generics & inheritance' },
            { type: 'doc', id: 'schema/branch-awareness', label: 'Branch awareness' },
            { type: 'doc', id: 'schema/hierarchy', label: 'Hierarchy' },
            { type: 'doc', id: 'schema/extensions', label: 'Schema extensions' },
          ],
        },
        // ── Schema operations ─────────────────────────────────
        {
          type: 'category',
          label: 'Schema operations',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'schema/create-and-load', label: 'Create and load schema' },
            { type: 'doc', id: 'schema/migration', label: 'Schema migration' },
            { type: 'doc', id: 'schema/marketplace/index', label: 'Marketplace' },
          ],
        },
        // ── Advanced schema features ──────────────────────────
        {
          type: 'category',
          label: 'Advanced schema features',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'computed-attributes/overview', label: 'Computed attributes' },
            { type: 'doc', id: 'schema/number-pool', label: 'Number pools' },
            { type: 'doc', id: 'schema/file-object', label: 'File objects' },
          ],
        },
        // ── Display & presentation ────────────────────────────
        {
          type: 'category',
          label: 'Display & presentation',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'schema/field-visibility', label: 'Field visibility' },
            { type: 'doc', id: 'schema/display_label', label: 'Display labels' },
            { type: 'doc', id: 'schema/order-weight', label: 'Order weight' },
            { type: 'doc', id: 'menu/overview', label: 'Menu customization' },
          ],
        },
        {
          type: 'category',
          label: 'Objects',
          link: { type: 'doc', id: 'objects/overview' }, // hub
          items: [
            { type: 'doc', id: 'objects/convert-object-kind', label: 'Convert object kind' },
            { type: 'doc', id: 'objects/metadata', label: 'Metadata & lineage' },
            { type: 'doc', id: 'objects/load-from-yaml', label: 'Load data in bulk using YAML file' },
          ],
        },
        {
          type: 'category',
          label: 'IPAM',
          link: { type: 'doc', id: 'ipam/overview' },
          items: [
            'ipam/ip-namespaces',
            'ipam/building-your-schema',
            'ipam/automate-with-resource-manager',
          ],
        },
        {
          type: 'category',
          label: 'Resource Manager',
          link: { type: 'doc', id: 'resource-manager/overview' }, // hub
          items: [
            'resource-manager/allocate-ip-address',
            'resource-manager/allocate-ip-prefix',
            'resource-manager/allocate-number',
            'resource-manager/weighted-allocation',
          ],
        },
        {
          type: 'category',
          label: 'Groups',
          link: { type: 'doc', id: 'groups/overview' }, // hub
          items: [
            'groups/create',
            'groups/add-members',
            'groups/remove-members',
            'groups/delete',
            'groups/query-members',
            'groups/use-in-automation',
          ],
        },
        {
          type: 'category',
          label: 'Profiles',
          link: { type: 'doc', id: 'profiles/overview' }, // hub
          items: [
            'profiles/priority-and-inheritance',
            'profiles/create',
            'profiles/assign',
            'profiles/override-values',
            'profiles/update',
            'profiles/use-multiple',
          ],
        },
        {
          type: 'category',
          label: 'Object Templates',
          link: { type: 'doc', id: 'object-templates/overview' }, // hub
          items: [
            { type: 'doc', id: 'object-templates/use', label: 'Use object templates' },
            { type: 'doc', id: 'object-templates/with-profiles', label: 'Assign Profiles to a template' },
            { type: 'doc', id: 'object-templates/allocate-resources-from-pools', label: 'Allocate resources from pools' },
          ],
        },
      ],
    },

    {
      type: 'category',
      label: 'Branches & Change Control',
      collapsible: false,
      collapsed: false,
      link: { type: 'generated-index', slug: 'branches-and-change-control' },
      items: [
        { type: 'doc', id: 'immutable-history/overview', label: 'Immutable History' },
        {
          type: 'category',
          label: 'Branches',
          link: { type: 'doc', id: 'branches/overview' }, // hub
          items: [
            'branches/create',
            'branches/merge',
            'branches/rebase',
            'branches/delete',
            'branches/resolve-conflicts',
          ],
        },
        {
          type: 'category',
          label: 'Proposed Changes',
          link: { type: 'doc', id: 'proposed-changes/overview' }, // hub
          items: [
            'proposed-changes/lifecycle',
            'proposed-changes/review-and-stamp',
            'proposed-changes/resolve-conflict',
          ],
        },
        { type: 'doc', id: 'checks/overview', label: 'Checks & Validation' },
        { type: 'doc', id: 'testing-framework/overview', label: 'Testing Framework' },
        { type: 'doc', id: 'change-approval/change-approval-workflow', label: 'Change Approval Policy' },
        {
          type: 'category',
          label: 'Git Integration',
          link: { type: 'doc', id: 'git-integration/overview' }, // hub
          items: [
            { type: 'doc', id: 'git-integration/connect-repository', label: 'Connect a repository' },
            { type: 'doc', id: 'git-integration/infrahub-yml', label: 'infrahub.yml configuration' },
            { type: 'doc', id: 'git-integration/branch-synchronization', label: 'Branch synchronization' },
          ],
        },
      ],
    },

    {
      type: 'category',
      label: 'Design & Integrate',
      collapsible: false,
      collapsed: false,
      link: { type: 'generated-index', slug: 'automation-and-outputs' },
      items: [
        {
          type: 'category',
          label: 'Generators',
          link: { type: 'doc', id: 'generators/overview' }, // hub
          items: [
            { type: 'doc', id: 'generators/build', label: 'Build a generator' },
            { type: 'doc', id: 'generators/modular', label: 'Modular generators' },
            { type: 'doc', id: 'generators/modular-best-practices', label: 'Modular generator best practices' },
          ],
        },
        {
          type: 'category',
          label: 'Transformations',
          link: { type: 'doc', id: 'transformations/overview' }, // hub
          items: [
            { type: 'doc', id: 'transformations/jinja2', label: 'Jinja2' },
            { type: 'doc', id: 'transformations/python', label: 'Python' },
          ],
        },
        {
          type: 'category',
          label: 'Artifacts',
          link: { type: 'doc', id: 'artifacts/overview' }, // hub
          items: [
            { type: 'doc', id: 'artifacts/use', label: 'Use artifacts' },
            { type: 'doc', id: 'artifacts/content-composition', label: 'Artifact content composition' },
          ],
        },
        {
          type: 'category',
          label: 'Artifact & File Storage',
          link: { type: 'doc', id: 'artifact-file-storage/overview' }, // hub (renamed from "Object Storage")
          items: [
            { type: 'doc', id: 'artifact-file-storage/configure', label: 'Configure storage' },
          ],
        },
        {
          type: 'category',
          label: 'Events',
          link: { type: 'doc', id: 'events/overview' }, // hub
          items: [
            { type: 'doc', id: 'events/event-system', label: 'Event system' },
            { type: 'doc', id: 'events/event-rules', label: 'Event rules' },
            { type: 'doc', id: 'events/event-actions', label: 'Event actions' },
          ],
        },
        {
          type: 'category',
          label: 'Webhooks',
          link: { type: 'doc', id: 'webhooks/overview' }, // hub
          items: [
            { type: 'doc', id: 'webhooks/create', label: 'Create a webhook' },
            { type: 'doc', id: 'webhooks/custom-transformation', label: 'Webhook with custom Transformation' },
          ],
        },
        {
          type: 'category',
          label: 'Integrations',
          link: { type: 'generated-index', slug: 'integrations-overview' },
          items: [
            { type: 'link', label: 'Ansible Integration ↗', href: 'https://docs.infrahub.app/ansible' },
            { type: 'link', label: 'Nornir Integration ↗', href: 'https://docs.infrahub.app/nornir' },
            { type: 'link', label: 'Infrahub Sync ↗', href: 'https://docs.infrahub.app/sync' },
          ],
        },
      ],
    },

    {
      type: 'category',
      label: 'Deployment & Management',
      collapsible: false,
      collapsed: false,
      link: { type: 'generated-index', slug: 'deployment-and-management' },
      items: [
        // ── Install & configure ──────────────────────────────────────────────
        {
          type: 'category',
          label: 'Install & configure',
          collapsible: true,
          collapsed: true,
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'deploy-manage/install-configure/hardware-requirements', label: 'Hardware requirements' },
            // Installation hub + spokes (PR 2)
            {
              type: 'category',
              label: 'Installation',
              link: { type: 'doc', id: 'deploy-manage/install-configure/install/overview' },
              items: [
                { type: 'doc', id: 'deploy-manage/install-configure/install/community', label: 'Community' },
                { type: 'doc', id: 'deploy-manage/install-configure/install/enterprise', label: 'Enterprise' },
                { type: 'doc', id: 'deploy-manage/install-configure/install/observability-stack', label: 'Observability stack' },
              ],
            },
            // Production Deployment hub + HA spoke (PR 3)
            {
              type: 'category',
              label: 'Production deployment',
              link: { type: 'doc', id: 'deploy-manage/install-configure/production-deployment/overview' },
              items: [
                { type: 'doc', id: 'deploy-manage/install-configure/production-deployment/high-availability', label: 'High availability' },
              ],
            },
            // Configure Infrahub (PR 4)
            { type: 'doc', id: 'deploy-manage/install-configure/configure-infrahub', label: 'Configure Infrahub' },
            // Configuration reference — stays in reference/, cross-linked here (PR 4)
            { type: 'ref', id: 'reference/configuration', label: 'Configuration reference' },
          ],
        },
        // ── Run & observe ────────────────────────────────────────────────────
        {
          type: 'category',
          label: 'Run & observe',
          collapsible: true,
          collapsed: true,
          link: { type: 'generated-index' },
          items: [
            // Tasks (PRs 5/6/7)
            { type: 'doc', id: 'deploy-manage/run-observe/tasks', label: 'Tasks' },
            // Telemetry (PRs 5/6/7)
            { type: 'doc', id: 'deploy-manage/run-observe/telemetry', label: 'Telemetry' },
            // Activity Log (PRs 5/6/7)
            { type: 'doc', id: 'deploy-manage/run-observe/activity-log', label: 'Activity log' },
            // Log Forwarding hub + spoke (PR 8)
            {
              type: 'category',
              label: 'Log forwarding',
              link: { type: 'doc', id: 'deploy-manage/run-observe/log-forwarding/overview' },
              items: [
                { type: 'doc', id: 'deploy-manage/run-observe/log-forwarding/configure-log-forwarding', label: 'Configure log forwarding' },
              ],
            },
          ],
        },
        // ── Maintain & upgrade ───────────────────────────────────────────────
        {
          type: 'category',
          label: 'Maintain & upgrade',
          collapsible: true,
          collapsed: true,
          link: { type: 'generated-index' },
          items: [
            // Database Backup hub + spokes (PR 9)
            {
              type: 'category',
              label: 'Database backup',
              link: { type: 'doc', id: 'deploy-manage/maintain-upgrade/database-backup/overview' },
              items: [
                { type: 'doc', id: 'deploy-manage/maintain-upgrade/database-backup/backup-and-restore', label: 'Backup and restore' },
                { type: 'doc', id: 'deploy-manage/maintain-upgrade/database-backup/cluster-backup-and-restore', label: 'Cluster backup and restore' },
              ],
            },
            // Upgrade hub + spokes (PR 10)
            {
              type: 'category',
              label: 'Upgrade',
              link: { type: 'doc', id: 'deploy-manage/maintain-upgrade/upgrade/overview' },
              items: [
                { type: 'doc', id: 'deploy-manage/maintain-upgrade/upgrade/community', label: 'Community' },
                { type: 'doc', id: 'deploy-manage/maintain-upgrade/upgrade/enterprise', label: 'Enterprise' },
                { type: 'doc', id: 'deploy-manage/maintain-upgrade/upgrade/observability-stack', label: 'Observability stack' },
              ],
            },
          ],
        },
        // ── User Management & Security ───────────────────────────────────────
        {
          type: 'category',
          label: 'User Management & Security',
          collapsible: true,
          collapsed: true,
          link: { type: 'generated-index' },
          items: [
            // Authentication (PR 11)
            { type: 'doc', id: 'deploy-manage/user-management/authentication', label: 'Authentication' },
            // SSO hub + spokes (PR 12)
            {
              type: 'category',
              label: 'Single sign-on (SSO)',
              link: { type: 'doc', id: 'deploy-manage/user-management/sso/overview' },
              items: [
                { type: 'doc', id: 'deploy-manage/user-management/sso/configure-sso', label: 'Configure SSO' },
                { type: 'doc', id: 'deploy-manage/user-management/sso/advanced-sso', label: 'Advanced SSO configuration' },
              ],
            },
            // Permissions & Roles hub + spoke (PR 13)
            {
              type: 'category',
              label: 'Permissions & roles',
              link: { type: 'doc', id: 'deploy-manage/user-management/permissions-roles/overview' },
              items: [
                { type: 'doc', id: 'deploy-manage/user-management/permissions-roles/manage-accounts-and-permissions', label: 'Manage accounts and permissions' },
              ],
            },
            // Managing API Tokens (PR 14)
            { type: 'doc', id: 'deploy-manage/user-management/managing-api-tokens', label: 'Managing API tokens' },
          ],
        },
      ],
    },

    {
      type: 'category',
      label: 'Development Resources',
      collapsible: false,
      collapsed: false,
      link: { type: 'generated-index', slug: 'development-resources' },
      items: [
        { type: 'doc', id: 'development-resources/developer-guide', label: 'Developer Guide' },
        {
          type: 'category',
          label: 'APIs & interfaces',
          collapsible: true,
          collapsed: true,
          items: [
            {
              type: 'category',
              label: 'GraphQL',
              link: { type: 'doc', id: 'development-resources/graphql/overview' },
              items: [
                { type: 'doc', id: 'development-resources/graphql/queries-and-mutations', label: 'Queries & mutations' },
                { type: 'doc', id: 'development-resources/graphql/stored-queries', label: 'Stored queries' },
                { type: 'doc', id: 'development-resources/graphql/single-target-queries', label: 'Single-target queries' },
                { type: 'doc', id: 'development-resources/graphql/groups', label: 'Working with groups' },
              ],
            },
            { type: 'doc', id: 'development-resources/graphql-fragments', label: 'GraphQL fragments' },
            { type: 'link', label: 'Python SDK ↗', href: 'https://docs.infrahub.app/python-sdk' },
            { type: 'link', label: 'Infrahubctl CLI ↗', href: 'https://docs.infrahub.app/infrahubctl' },
            { type: 'link', label: 'MCP Server ↗', href: 'https://docs.infrahub.app/mcp' },
          ],
        },
      ],
    },

    {
      type: 'category',
      label: 'Reference',
      collapsible: false,
      collapsed: false,
      link: {
        type: 'generated-index',
        slug: 'reference',
      },
      items: [
        {
          type: 'category',
          label: 'Schema Specification',
          link: {
            type: 'generated-index',
            slug: 'reference/schema',
          },
          items: [
            'reference/schema/node',
            'reference/schema/node-extension',
            'reference/schema/attribute',
            // { type: 'doc', id: 'topics/schema-attr-kind-number-pool', label: 'Attribute - NumberPool' },
            'reference/schema/relationship',
            'reference/schema/generic',
            'reference/schema/groups',
            'reference/schema/validator-migration',
            'reference/schema-validation',
          ],
        },
        {
          type: 'category',
          label: 'CLI',
          link: {
            type: 'generated-index',
            slug: 'reference/infrahub-cli',
          },
          items: [
            'reference/infrahub-cli/infrahub-db',
            'reference/infrahub-cli/infrahub-server',
            'reference/infrahub-cli/infrahub-dev',
            'reference/infrahub-cli/infrahub-upgrade',
          ],
        },
        {
          type: 'category',
          label: 'Configuration Files',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'reference/configuration', label: 'Infrahub Configuration' },
            { type: 'doc', id: 'reference/dotinfrahub', label: 'Repository Config' },
            { type: 'doc', id: 'reference/menu', label: 'Menu Configuration' },
            { type: 'doc', id: 'reference/infrahub-tests', label: 'Tests Configuration' },
          ],
        },
        {
          type: 'category',
          label: 'Events',
          link: { type: 'doc', id: 'reference/infrahub-events/overview' },
          items: [
            { type: 'doc', id: 'reference/infrahub-events/account', label: 'Account events' },
            { type: 'doc', id: 'reference/infrahub-events/artifact', label: 'Artifact events' },
            { type: 'doc', id: 'reference/infrahub-events/branch', label: 'Branch events' },
            { type: 'doc', id: 'reference/infrahub-events/commit', label: 'Commit events' },
            { type: 'doc', id: 'reference/infrahub-events/group', label: 'Group events' },
            { type: 'doc', id: 'reference/infrahub-events/node', label: 'Node events' },
            { type: 'doc', id: 'reference/infrahub-events/proposed', label: 'Proposed change events' },
            { type: 'doc', id: 'reference/infrahub-events/schema', label: 'Schema events' },
            { type: 'doc', id: 'reference/infrahub-events/validator', label: 'Validator events' },
          ],
        },
        {
          type: 'category',
          label: 'Permissions',
          link: { type: 'generated-index' },
          items: [
            'reference/permissions',
          ],
        },
        {
          type: 'category',
          label: 'Authentication',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'reference/sso', label: 'SSO Reference' },
          ],
        },
        { type: 'doc', id: 'reference/message-bus-events', label: 'Message Bus Events' },
      ],
    },

    {
      type: 'category',
      label: 'Project',
      collapsible: false,
      collapsed: false,
      items: [
        {
          type: 'category',
          label: 'Contributing',
          collapsible: true,
          collapsed: true,
          link: {
            type: 'generated-index',
            slug: 'development',
          },
          items: [
            'development/git-best-practices',
            'development/editor',
            'development/changelog',
            'development/backend',
            {
              type: 'category',
              label: 'Frontend guide',
              link: { type: 'doc', id: 'development/frontend/readme' },
              items: [
                'development/frontend/getting-set-up',
                'development/frontend/testing-guidelines',
              ],
            },
            { type: 'doc', id: 'development-resources/local-demo-environment', label: 'Local Demo Environment' },
            'development/docs',
            'development/style-guide',
          ],
        },
        {
          type: 'category',
          label: 'Release Notes',
          collapsible: true,
          collapsed: true,
          link: {
            type: 'generated-index',
            slug: 'release-notes',
          },
          items: [
            {
              type: 'category',
              label: 'Infrahub',
              link: {
                type: 'generated-index',
                slug: 'release-notes/infrahub',
              },
              items: [
                { type: 'doc', id: 'release-notes/infrahub/docs-restructure', label: 'Documentation restructure' },
                'release-notes/infrahub/release-1_9_8',
                'release-notes/infrahub/release-1_9_7',
                'release-notes/infrahub/release-1_9_6',
                'release-notes/infrahub/release-1_9_5',
                'release-notes/infrahub/release-1_9_4',
                'release-notes/infrahub/release-1_9_3',
                'release-notes/infrahub/release-1_9_2',
                'release-notes/infrahub/release-1_9_1',
                'release-notes/infrahub/release-1_9_0',
                'release-notes/infrahub/release-1_8_6',
                'release-notes/infrahub/release-1_8_5',
                'release-notes/infrahub/release-1_8_4',
                'release-notes/infrahub/release-1_8_3',
                'release-notes/infrahub/release-1_8_2',
                'release-notes/infrahub/release-1_8_1',
                'release-notes/infrahub/release-1_8_0',
                'release-notes/infrahub/release-1_7_7',
                'release-notes/infrahub/release-1_7_6',
                'release-notes/infrahub/release-1_7_5',
                'release-notes/infrahub/release-1_7_4',
                'release-notes/infrahub/release-1_7_3',
                'release-notes/infrahub/release-1_7_2',
                'release-notes/infrahub/release-1_7_1',
                'release-notes/infrahub/release-1_7_0',
                'release-notes/infrahub/release-1_6_3',
                'release-notes/infrahub/release-1_6_2',
                'release-notes/infrahub/release-1_6_1',
                'release-notes/infrahub/release-1_6_0',
                'release-notes/infrahub/release-1_5_3',
                'release-notes/infrahub/release-1_5_2',
                'release-notes/infrahub/release-1_5_1',
                'release-notes/infrahub/release-1_5_0',
                'release-notes/infrahub/release-1_4_13',
                'release-notes/infrahub/release-1_4_12',
                'release-notes/infrahub/release-1_4_11',
                'release-notes/infrahub/release-1_4_10',
                'release-notes/infrahub/release-1_4_9',
                'release-notes/infrahub/release-1_4_8',
                'release-notes/infrahub/release-1_4_7',
                'release-notes/infrahub/release-1_4_6',
                'release-notes/infrahub/release-1_4_5',
                'release-notes/infrahub/release-1_4_4',
                'release-notes/infrahub/release-1_4_3',
                'release-notes/infrahub/release-1_4_2',
                'release-notes/infrahub/release-1_4_1',
                'release-notes/infrahub/release-1_4_0',
                'release-notes/infrahub/release-1_3_7',
                'release-notes/infrahub/release-1_3_6',
                'release-notes/infrahub/release-1_3_5',
                'release-notes/infrahub/release-1_3_3',
                'release-notes/infrahub/release-1_3_2',
                'release-notes/infrahub/release-1_3_1',
                'release-notes/infrahub/release-1_3_0',
                'release-notes/infrahub/release-1_2_12',
                'release-notes/infrahub/release-1_2_11',
                'release-notes/infrahub/release-1_2_10',
                'release-notes/infrahub/release-1_2_9',
                'release-notes/infrahub/release-1_2_8',
                'release-notes/infrahub/release-1_2_7',
                'release-notes/infrahub/release-1_2_6',
                'release-notes/infrahub/release-1_2_5',
                'release-notes/infrahub/release-1_2_4',
                'release-notes/infrahub/release-1_2_3',
                'release-notes/infrahub/release-1_2_2',
                'release-notes/infrahub/release-1_2_1',
                'release-notes/infrahub/release-1_2_0',
                'release-notes/infrahub/release-1_1_9',
                'release-notes/infrahub/release-1_1_8',
                'release-notes/infrahub/release-1_1_7',
                'release-notes/infrahub/release-1_1_6',
                'release-notes/infrahub/release-1_1_5',
                'release-notes/infrahub/release-1_1_4',
                'release-notes/infrahub/release-1_1_3',
                'release-notes/infrahub/release-1_1_2',
                'release-notes/infrahub/release-1_1_1',
                'release-notes/infrahub/release-1_1_0',
                'release-notes/infrahub/release-1_0_10',
                'release-notes/infrahub/release-1_0_9',
                'release-notes/infrahub/release-1_0_8',
                'release-notes/infrahub/release-1_0_7',
                'release-notes/infrahub/release-1_0_6',
                'release-notes/infrahub/release-1_0_5',
                'release-notes/infrahub/release-1_0_4',
                'release-notes/infrahub/release-1_0_3',
                'release-notes/infrahub/release-1_0_2',
                'release-notes/infrahub/release-1_0_1',
                'release-notes/infrahub/release-1_0_0',
                'release-notes/infrahub/release-0_16_4',
                'release-notes/infrahub/release-0_16_3',
                'release-notes/infrahub/release-0_16_2',
                'release-notes/infrahub/release-0_16_1',
                'release-notes/infrahub/release-0_16_0',
                'release-notes/infrahub/release-0_15_3',
                'release-notes/infrahub/release-0_15_2',
                'release-notes/infrahub/release-0_15_1',
                'release-notes/infrahub/release-0_15_0',
                'release-notes/infrahub/release-0_14',
                'release-notes/infrahub/release-0_13',
                'release-notes/infrahub/release-0_12',
                'release-notes/infrahub/release-0_11',
                'release-notes/infrahub/release-0_10',
                'release-notes/infrahub/release-0_9',
                'release-notes/infrahub/release-0_8',
                'release-notes/infrahub/release-0_7',
                'release-notes/infrahub/release-0_6',
              ],
            },
            {
              type: 'category',
              label: 'Deprecation Guides',
              link: {
                type: 'generated-index',
                slug: 'release-notes/deprecation-guides',
              },
              items: [
                'release-notes/deprecation-guides/display_labels',
                'release-notes/deprecation-guides/sso-account-name-fallback',
              ],
            },
          ],
        },
      ],
    },
  ],
};

export default sidebars;
