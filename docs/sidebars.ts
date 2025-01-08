import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

/**
  * Creating a sidebar enables you to:
  - create an ordered group of docs
  - render a sidebar for each doc of that group
  - provide next/previous navigation

  The sidebars can be generated from the filesystem, or explicitly defined here.

  Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  docsSidebar: [
    'readme',
    {
      type: 'category',
      label: 'Infrahub Overview',
      link: { type: 'doc', id: 'overview/readme' },
      items: [
        'overview/interfaces',
        'overview/schema',
        'overview/data',
        'overview/transformations',
        'overview/versioning',
        'overview/generators',
        'overview/integrations',
      ],
    },
    {
      type: 'category',
      label: 'Tutorials',
      link: {
        type: 'generated-index',
        slug: 'tutorials'
      },
      items: [
        {
          type: 'category',
          label: 'Getting started',
          link: { type: 'doc', id: 'tutorials/getting-started/readme' },
          items: [
            'tutorials/getting-started/introduction-to-infrahub',
            'tutorials/getting-started/schema',
            'tutorials/getting-started/creating-an-object',
            'tutorials/getting-started/branches',
            'tutorials/getting-started/historical-data',
            'tutorials/getting-started/lineage-information',
            'tutorials/getting-started/resource-manager',
            'tutorials/getting-started/git-integration',
            'tutorials/getting-started/rendering-configuration',
            'tutorials/getting-started/graphql-query',
            'tutorials/getting-started/graphql-mutation'
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      link: {
        type: 'generated-index',
        slug: 'guides'
      },
      items: [
        'guides/installation',
        'guides/create-schema',
        'guides/import-schema',
        'guides/menu',
        'guides/accounts-permissions',
        'guides/groups',
        'guides/generator',
        'guides/repository',
        'guides/jinja2-transform',
        'guides/python-transform',
        'guides/artifact',
        'guides/database-backup',
        'guides/profiles',
        'guides/object-storage',
        'guides/sso',
        'guides/check',
        'guides/resource-manager',
        'guides/managing-api-tokens',
        'guides/computed-attributes',
      ],
    },
    {
      type: 'category',
      label: 'Topics',
      link: {
        type: 'generated-index',
        slug: 'topics'
      },
      items: [
        'topics/infrahub-yml',
        'topics/architecture',
        'topics/artifact',
        'topics/check',
        'topics/metadata',
        'topics/database-backup',
        'topics/developer-guide',
        'topics/local-demo-environment',
        'topics/generator',
        'topics/graphql',
        'topics/groups',
        'topics/hardware-requirements',
        'topics/version-control',
        'topics/ipam',
        'topics/object-storage',
        'topics/permissions-roles',
        'topics/profiles',
        'topics/proposed-change',
        'topics/repository',
        'topics/resource-manager',
        'topics/resources-testing-framework',
        'topics/schema',
        'topics/transformation',
        'topics/auth',
        'topics/computed-attributes',
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
        'reference/menu',
        {
          type: 'category',
          label: 'infrahub cli',
          link: {
            type: 'generated-index',
            slug: 'reference/infrahub-cli',
          },
          items: [
            'reference/infrahub-cli/infrahub-db',
            'reference/infrahub-cli/infrahub-git-agent',
            'reference/infrahub-cli/infrahub-server'
          ],
        },
        'reference/configuration',
        'reference/git-agent',
        'reference/message-bus-events',
        'reference/api-server',
        'reference/dotinfrahub',
        'reference/infrahub-tests',
        'reference/permissions',
        'reference/schema-validation'
      ],
    },
    {
      type: 'category',
      label: 'Python SDK',
      link: {
        type: 'doc',
        id: 'python-sdk/readme'
      },
      items: [
        {
          type: 'category',
          label: 'Guides',
          items: [
            'python-sdk/guides/installation',
            'python-sdk/guides/client',
            'python-sdk/guides/query_data',
            'python-sdk/guides/create_update_delete',
            'python-sdk/guides/branches',
            'python-sdk/guides/store',
            'python-sdk/guides/tracking',
            'python-sdk/guides/batch',
            'python-sdk/guides/object-storage',
            'python-sdk/guides/resource-manager'
          ],
        },
        {
          type: 'category',
          label: 'Topics',
          items: [
            'python-sdk/topics/tracking'
          ],
        },
        {
          type: 'category',
          label: 'Reference',
          items: [
            'python-sdk/reference/config'
          ],
        },
      ],
    },
    {
      type: 'category',
      label: 'infrahubctl',
      link: { type: 'doc', id: 'infrahubctl' },
      items: [{ type: 'autogenerated', dirName: 'infrahubctl' }],
    },
    {
      type: 'category',
      label: 'Integrations',
      link: {
        type: 'doc',
        id: 'integrations/readme'
      },
      items: [
        {
          type: 'category',
          label: 'Infrahub Ansible Collection',
          link: {
            type: 'doc',
            id: 'integrations/infrahub-ansible/readme'
          },
          items: [
            {
            },
          ],
        },
        {
          type: 'category',
          label: 'Infrahub Sync',
          link: {
            type: 'doc',
            id: 'integrations/sync/readme'
          },
          items: [
            {
              type: 'category',
              label: 'Guides',
              items: [
                'integrations/sync/guides/installation',
                'integrations/sync/guides/creation',
                'integrations/sync/guides/run',
              ],
            },
            {
              type: 'category',
              label: 'Reference',
              items: [
                'integrations/sync/reference/config',
                'integrations/sync/reference/cli',
              ],
            },
          ],
        },
        {
          type: 'category',
          label: 'Nornir plugin for Infrahub',
          link: {
            type: 'doc',
            id: 'integrations/nornir-infrahub/readme'
          },
          items: [
            {
            },
          ],
        },
      ]
    },
    {
      type: 'category',
      label: 'Development',
      link: {
        type: 'generated-index',
        slug: 'development'
      },

      items: [
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
          label: 'Python SDK',
          link: {
            type: 'generated-index',
            slug: 'release-notes/python-sdk',
          },
          items: [
            // 'release-notes/python-sdk/release-1_0-DRAFT',
            'release-notes/python-sdk/release-0_13'
          ],
        },
      ],
    },
    'faq/faq',
  ],
};

export default sidebars;
