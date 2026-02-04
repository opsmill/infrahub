import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    "home",
    {
      type: 'category',
      label: 'Getting Started',
      collapsed: false,
      collapsible: false,
      items: [
        'getting-started/overview',
        'getting-started/quick-start',
        'getting-started/next-steps',
        'getting-started/concepts',
      ],
    },
    {
      type: 'category',
      label: 'Academy',
      collapsed: false,
      collapsible: false,
      link: {
        type: 'doc',
        id: 'academy/academy'
      },
      items: [
        {
          type: 'category',
          label: 'Getting Started',
          link: {
            type: 'generated-index',
          },
          items: [
            'academy/getting-started/infrahub-introduction',
            'academy/getting-started/deploy-first-configuration',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      collapsed: false,
      collapsible: false,
      link: {
        type: 'generated-index',
        slug: 'guides'
      },
      items: [
        {
          type: 'category',
          label: 'Installation & Setup',
          link: {
            type: 'generated-index',
          },
          items: [
            'guides/installation',
            'guides/production-deployment',
            'guides/configuration-changes',
            'guides/database-backup',
            'guides/upgrade',
            'guides/repository',
            'guides/selective-branch-sync',
          ],
        },
        {
          type: 'category',
          label: 'Schema & Data Modeling',
          link: {
            type: 'generated-index',
          },
          items: [
            'guides/create-schema',
            'guides/import-schema',
            'guides/customize-field-ordering',
            'guides/menu',
            'guides/computed-attributes',
          ],
        },
        {
          type: 'category',
          label: 'Data Management',
          link: {
            type: 'generated-index',
          },
          items: [
            'guides/object-load',
            'guides/resource-manager',
            'guides/groups',
            'guides/object-template',
            'guides/profiles',
            'guides/check',
            'guides/object-conversion',
          ],
        },
        {
          type: 'category',
          label: 'Artifact & Transform',
          link: {
            type: 'generated-index',
          },
          items: [
            'guides/jinja2-transform',
            'guides/python-transform',
            'guides/artifact',
            'guides/object-storage',
          ],
        },
        {
          type: 'category',
          label: 'Generators',
          link: {
            type: 'generated-index',
          },
          items: [
            'guides/generator',
          ],
        },
        {
          type: 'category',
          label: 'Integration & Events',
          link: {
            type: 'generated-index',
          },
          items: [
            'guides/events-rules-actions',
            'guides/webhooks',
          ],
        },
        {
          type: 'category',
          label: 'User Management & Authentication',
          link: {
            type: 'generated-index',
          },
          items: [
            'guides/sso',
            'guides/managing-api-tokens',
            'guides/accounts-permissions',
            'guides/change-approval-workflow',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Topics',
      collapsed: false,
      collapsible: false,
      link: {
        type: 'generated-index',
        slug: 'topics'
      },
      items: [
        {
          type: 'category',
          label: 'Overview',
          link: {
            type: 'generated-index',
          },
          items: [
            'topics/architecture',
            'topics/community-vs-enterprise',
          ],
        },
        {
          type: 'category',
          label: 'Core Concepts',
          link: {
            type: 'generated-index',
          },
          items: [
            {
              type: 'category',
              label: 'Git Integration',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/infrahub-yml',
                'topics/repository',
                'topics/branch-synchronization',
              ],
            },
            {
              type: 'category',
              label: 'Transforms',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/transformation',
              ],
            },
            {
              type: 'category',
              label: 'Generators',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/generator',
              ],
            },
            {
              type: 'category',
              label: 'Version Control & Branching',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/version-control',
                'topics/branching',
                'topics/proposed-change',
              ],
            },
            {
              type: 'category',
              label: 'Artifacts',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/artifact',
                'topics/object-storage',
              ],
            },
            {
              type: 'category',
              label: 'Schema',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/schema',
                'topics/order-weight',
                'topics/schema-attr-kind-number-pool',
                'topics/computed-attributes',
                'topics/schema-extensions',
                'topics/labels',
              ],
            },
            {
              type: 'category',
              label: 'Data Management',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/check',
                'topics/metadata',
                'topics/groups',
                'topics/graphql',
                'topics/object-conversion',
                'topics/resource-manager',
                'topics/object-template',
                'topics/profiles',
              ],
            },
            {
              type: 'category',
              label: 'IPAM',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/ipam',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: 'Platform Capabilities',
          link: {
            type: 'generated-index',
          },
          items: [
            {
              type: 'category',
              label: 'User Management & Authentication',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/authentication',
                'topics/permissions-roles',
              ],
            },
            {
              type: 'category',
              label: 'Event Management & Logging',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/activity-log',
                'topics/events',
                'topics/event-actions',
                'topics/tasks',
                'topics/webhooks',
              ],
            },
            {
              type: 'category',
              label: 'System Administration',
              link: {
                type: 'generated-index',
              },
              items: [
                'topics/database-backup',
                'topics/hardware-requirements',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: 'Development Resources',
          link: {
            type: 'generated-index',
          },
          items: [
            'topics/developer-guide',
            'topics/local-demo-environment',
            'topics/resources-testing-framework',
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      link: {
        type: 'generated-index',
        slug: 'reference'
      },
      items: [
        'reference/api-server',
        'reference/configuration',
        {
          type: 'category',
          label: 'infrahub cli',
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
        'reference/infrahub-events',
        'reference/menu',
        'reference/message-bus-events',
        'reference/dotinfrahub', //Repository Configuration File
        'reference/permissions',

        {
          type: 'category',
          label: 'Schema',
          link: {
            type: 'generated-index',
            slug: 'reference/schema',
          },
          items: [
            'reference/schema/node',
            'reference/schema/node-extension',
            'reference/schema/attribute',
            'reference/schema/groups',
            'reference/schema/relationship',
            'reference/schema/generic',
            'reference/schema/validator-migration',
          ],
        },
        'reference/schema-validation',
        'reference/task-worker',
        'reference/infrahub-tests',
        'reference/sso'
      ],
    },
    {
      type: 'category',
      label: 'Contributing',
      link: {
        type: 'generated-index',
        slug: 'development'
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
        'development/docs'
      ],
    },
    {
      type: 'category',
      label: 'Release Notes',
      link: {
        type: 'generated-index',
        slug: 'release-notes'
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
            'release-notes/infrahub/release-0_6'
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
    'faq/faq',
  ],
};

export default sidebars;
