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
            { type: 'doc', id: 'topics/architecture', label: 'Architecture' },
            { type: 'doc', id: 'topics/community-vs-enterprise', label: 'Community vs Enterprise' },
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
          link: { type: 'doc', id: 'schema/index' }, // hub
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
          ],
        },
        // ── Extended schema kinds ─────────────────────────────
        {
          type: 'category',
          label: 'Extended schema kinds',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'computed-attributes/index', label: 'Computed attributes' },
            { type: 'doc', id: 'schema/number-pool', label: 'Number pool attribute' },
            { type: 'doc', id: 'schema/file-object', label: 'File object node' },
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
            { type: 'doc', id: 'menu/index', label: 'Menu customization' },
          ],
        },
        {
          type: 'category',
          label: 'Templates', // [Object Blueprints — rename pending]
          link: { type: 'doc', id: 'topics/object-template' }, // hub
          items: [
            { type: 'doc', id: 'guides/object-template', label: 'Use Templates' },
          ],
        },
        {
          type: 'category',
          label: 'Resource Manager',
          link: { type: 'doc', id: 'resource-manager/index' }, // hub
          items: [
            'resource-manager/allocate-ip-address',
            'resource-manager/allocate-ip-prefix',
            'resource-manager/allocate-number',
            'resource-manager/weighted-allocation',
          ],
        },
        {
          type: 'category',
          label: 'IPAM',
          link: { type: 'doc', id: 'ipam/index' },
          items: [
            'ipam/ip-namespaces',
            'ipam/building-your-schema',
            'ipam/automate-with-resource-manager',
          ],
        },
        {
          type: 'category',
          label: 'Objects',
          link: { type: 'generated-index' }, // About Objects hub page not yet authored
          items: [
            { type: 'doc', id: 'topics/object-conversion', label: 'Convert object kind' },
            { type: 'doc', id: 'topics/metadata', label: 'Metadata & lineage' },
            { type: 'doc', id: 'guides/object-load', label: 'Load data from YAML file' },
          ],
        },
        {
          type: 'category',
          label: 'Groups',
          link: { type: 'doc', id: 'groups/index' }, // hub
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
          link: { type: 'doc', id: 'profiles/index' }, // hub
          items: [
            'profiles/priority-and-inheritance',
            'profiles/create',
            'profiles/assign',
            'profiles/override-values',
            'profiles/update',
            'profiles/use-multiple',
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
        { type: 'doc', id: 'topics/version-control', label: 'Immutable History' },
        {
          type: 'category',
          label: 'Branches',
          link: { type: 'doc', id: 'branches/index' }, // hub
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
          link: { type: 'doc', id: 'proposed-changes/index' }, // hub
          items: [
            'proposed-changes/lifecycle',
            'proposed-changes/review-and-stamp',
            'proposed-changes/resolve-conflict',
          ],
        },
        { type: 'doc', id: 'checks/index', label: 'Checks & Validation' },
        { type: 'doc', id: 'change-approval/change-approval-workflow', label: 'Change Approval Policy' },
        {
          type: 'category',
          label: 'Git Integration',
          link: { type: 'doc', id: 'git-integration/index' }, // hub
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
      label: 'Automation & Outputs',
      collapsible: false,
      collapsed: false,
      link: { type: 'generated-index', slug: 'automation-and-outputs' },
      items: [
        {
          type: 'category',
          label: 'Generators',
          link: { type: 'doc', id: 'topics/generator' }, // hub
          items: [
            { type: 'doc', id: 'guides/generator', label: 'Build a generator' },
            { type: 'doc', id: 'guides/chaining-generators', label: 'Chaining generators' },
            { type: 'doc', id: 'topics/modular-generators', label: 'Modular generators' },
            { type: 'doc', id: 'guides/modular-generator-best-practices', label: 'Modular generator best practices' },
          ],
        },
        {
          type: 'category',
          label: 'Transformations',
          link: { type: 'doc', id: 'topics/transformation' }, // hub
          items: [
            { type: 'doc', id: 'guides/jinja2-transform', label: 'Write a Jinja2 transformation' },
            { type: 'doc', id: 'guides/python-transform', label: 'Write a Python transformation' },
          ],
        },
        {
          type: 'category',
          label: 'Artifacts',
          link: { type: 'doc', id: 'topics/artifact' }, // hub
          items: [
            { type: 'doc', id: 'guides/artifact', label: 'Use artifacts' },
            { type: 'doc', id: 'guides/artifact-content-composition', label: 'Artifact content composition' },
          ],
        },
        {
          type: 'category',
          label: 'Artifact & File Storage',
          link: { type: 'doc', id: 'topics/object-storage' }, // hub (renamed from "Object Storage")
          items: [
            { type: 'doc', id: 'guides/object-storage', label: 'Configure storage' },
          ],
        },
        {
          type: 'category',
          label: 'Events',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'topics/events', label: 'Events System' },
            { type: 'doc', id: 'topics/event-actions', label: 'Event Actions' },
            { type: 'doc', id: 'guides/events-rules-actions', label: 'Rules & Actions' },
          ],
        },
        {
          type: 'category',
          label: 'Webhooks',
          link: { type: 'doc', id: 'topics/webhooks' }, // hub
          items: [
            { type: 'doc', id: 'guides/webhooks', label: 'Use Webhooks' },
          ],
        },
        {
          type: 'category',
          label: 'Integrations',
          link: { type: 'generated-index' },
          items: [
            { type: 'link', label: 'Ansible Integration ↗', href: 'https://TODO-FILL-IN-ansible.example.com' },
            { type: 'link', label: 'Nornir Integration ↗', href: 'https://TODO-FILL-IN-nornir.example.com' },
            { type: 'link', label: 'Infrahub Sync ↗', href: 'https://TODO-FILL-IN-infrahub-sync.example.com' },
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
      // Internal sub-grouping (Plan & install / Configure / Run / Observe /
      // Maintain & upgrade) deferred — Fatih hasn't picked an option yet.
      // Flat layout for now; sub-groupings added in follow-up PRs once chosen.
      items: [
        { type: 'doc', id: 'topics/hardware-requirements', label: 'Hardware requirements' },
        { type: 'doc', id: 'guides/installation', label: 'Installation' },
        { type: 'doc', id: 'guides/production-deployment', label: 'Production deployment' },
        { type: 'doc', id: 'reference/configuration', label: 'Configuration' },
        { type: 'doc', id: 'guides/configuration-changes', label: 'Configuration changes' },
        { type: 'doc', id: 'topics/tasks', label: 'Tasks' },
        { type: 'doc', id: 'reference/task-worker', label: 'Task worker' },
        { type: 'doc', id: 'guides/telemetry', label: 'Telemetry' },
        { type: 'doc', id: 'topics/activity-log', label: 'Activity log' },
        { type: 'doc', id: 'topics/log-forwarding', label: 'Log forwarding' },
        { type: 'doc', id: 'topics/database-backup', label: 'Database backup' },
        { type: 'doc', id: 'guides/upgrade', label: 'Upgrade' },
        { type: 'link', label: 'Infrahub Backup Tool ↗', href: 'https://TODO-FILL-IN-infrahub-backup.example.com' },
        {
          type: 'category',
          label: 'User Management & Security',
          link: { type: 'generated-index' },
          items: [
            { type: 'doc', id: 'topics/authentication', label: 'Authentication' },
            { type: 'doc', id: 'guides/sso', label: 'SSO' },
            { type: 'doc', id: 'topics/permissions-roles', label: 'Permissions & Roles' },
            { type: 'doc', id: 'guides/managing-api-tokens', label: 'Managing API Tokens' },
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
        { type: 'doc', id: 'topics/developer-guide', label: 'Developer Guide' },
        { type: 'doc', id: 'topics/local-demo-environment', label: 'Local Demo Environment' },
        { type: 'doc', id: 'topics/resources-testing-framework', label: 'Testing Framework' },
        {
          type: 'category',
          label: 'APIs & interfaces',
          collapsible: true,
          collapsed: true,
          items: [
            { type: 'doc', id: 'topics/graphql', label: 'GraphQL' },
            { type: 'doc', id: 'guides/graphql-fragment', label: 'GraphQL fragments' },
            { type: 'ref', id: 'reference/api-server', label: 'REST API' },
            { type: 'link', label: 'Python SDK ↗', href: 'https://TODO-FILL-IN-python-sdk.example.com' },
            { type: 'link', label: 'Infrahubctl CLI ↗', href: 'https://TODO-FILL-IN-infrahubctl.example.com' },
            { type: 'link', label: 'MCP Server ↗', href: 'https://TODO-FILL-IN-mcp-server.example.com' },
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
          label: 'API',
          link: { type: 'generated-index' },
          items: [
            'reference/api-server',
            'reference/message-bus-events',
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
          label: 'Schema Specification',
          link: {
            type: 'generated-index',
            slug: 'reference/schema',
          },
          items: [
            'reference/schema/node',
            'reference/schema/node-extension',
            'reference/schema/attribute',
            { type: 'doc', id: 'topics/schema-attr-kind-number-pool', label: 'Attribute - NumberPool' },
            'reference/schema/relationship',
            'reference/schema/generic',
            'reference/schema/groups',
            'reference/schema/validator-migration',
            'reference/schema-validation',
          ],
        },
        {
          type: 'category',
          label: 'Events',
          link: { type: 'generated-index' },
          items: [
            'reference/infrahub-events',
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
            // Cross-link to Development Resources
            { type: 'ref', id: 'topics/local-demo-environment', label: 'Local Demo Environment' },
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
              ],
            },
          ],
        },
      ],
    },
  ],
};

export default sidebars;
