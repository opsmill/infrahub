import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: 'Academy',
      collapsible: false,
      collapsed: false,
      items: [
        {
          type: 'category',
          label: 'Tutorials',
          link: { type: 'generated-index' },
          items: [
            'schema-and-data/academy/tutorials/build-your-first-schema',
          ],
        },
      ],
    },

    {
      type: 'category',
      label: 'Schema and Data',
      collapsible: false,
      collapsed: false,
      items: [
        {
          type: 'category',
          label: 'Schema concepts',
          link: { type: 'doc', id: 'schema-and-data/schema-concepts/about-schema' },
          items: [
            'schema-and-data/schema-concepts/nodes-and-attributes',
            'schema-and-data/schema-concepts/about-relationships',
            'schema-and-data/schema-concepts/generics-and-inheritance',
            'schema-and-data/schema-concepts/schema-behaviors',
          ],
        },

        {
          type: 'category',
          label: 'Schema operations',
          collapsible: true,
          collapsed: false,
          items: [
            'schema-and-data/schema-operations/create-and-load-schema',
            'schema-and-data/schema-operations/schema-migration',
            'schema-and-data/schema-operations/schema-extensions',
          ],
        },

        {
          type: 'category',
          label: 'Extended types',
          collapsible: true,
          collapsed: false,
          items: [
            'schema-and-data/extended-types/computed-attribute',
            'schema-and-data/extended-types/number-pool-attribute',
            'schema-and-data/extended-types/object-file-node',
          ],
        },

        {
          type: 'category',
          label: 'Display & presentation',
          collapsible: true,
          collapsed: false,
          items: [
            'schema-and-data/display-and-presentation/controlling-field-visibility',
            'schema-and-data/display-and-presentation/labels',
            'schema-and-data/display-and-presentation/order-weight',
            'schema-and-data/display-and-presentation/menu-customization',
          ],
        },

        {
          type: 'category',
          label: 'Objects',
          link: { type: 'doc', id: 'schema-and-data/objects/index' },
          items: [
            'schema-and-data/objects/convert-object-kind',
            'schema-and-data/objects/metadata-and-lineage',
            'schema-and-data/objects/load-data-in-bulk',
          ],
        },

        { type: 'doc', id: 'schema-and-data/groups/index', label: 'Groups' },
        { type: 'doc', id: 'schema-and-data/profiles/index', label: 'Profiles' },
        { type: 'doc', id: 'schema-and-data/ipam/index', label: 'IPAM' },

        {
          type: 'category',
          label: 'Resource Manager',
          link: { type: 'doc', id: 'schema-and-data/resource-manager/index' },
          items: [
            'schema-and-data/resource-manager/allocate-ip-addresses',
            'schema-and-data/resource-manager/allocate-ip-prefixes',
            'schema-and-data/resource-manager/allocate-numbers',
            'schema-and-data/resource-manager/advanced-allocation-patterns',
          ],
        },

        {
          type: 'category',
          label: 'Object Templates',
          link: { type: 'doc', id: 'schema-and-data/object-templates/index' },
          items: [
            'schema-and-data/object-templates/use-templates',
            'schema-and-data/object-templates/templates-with-profiles',
            'schema-and-data/object-templates/allocate-resources-via-templates',
          ],
        },
      ],
    },
  ],
};

export default sidebars;
