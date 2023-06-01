export const deviceDetailsMocksId = "bd3110b9-5923-45e9-b643-776b8151c074";
export const deviceDetailsMocksASNName = "AS64496 64496";
export const deviceDetailsMocksOwnerName = "Engineering Team";
export const deviceDetailsMocksTagName = "green";

export const deviceDetailsMocksSchema = [
  {
    id: "b51a0359-8216-4c95-b073-8d0578fa6b17",
    name: "device",
    kind: "Device",
    description: null,
    default_filter: "name__value",
    order_by: ["name__value"],
    display_labels: ["name__value"],
    attributes: [
      {
        id: "8788dcb2-821c-4046-8ddc-2bb1ca545386",
        name: "name",
        kind: "Text",
        label: "Name",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: true,
        branch: true,
        optional: false,
        order_weight: 1000,
      },
      {
        id: "a7d6e9a5-c958-47a8-9d45-6b4a6bee1eac",
        name: "description",
        kind: "Text",
        label: "Description",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 2000,
      },
      {
        id: "31d22a0b-95cc-450d-b9c6-aff6fee6c0c1",
        name: "type",
        kind: "Text",
        label: "Type",
        description: null,
        default_value: null,
        enum: null,
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 3000,
      },
    ],
    relationships: [
      {
        id: "90d475cb-26d7-4a9d-986a-5a9c25d51c58",
        name: "site",
        peer: "Location",
        kind: "Attribute",
        label: "Site",
        description: null,
        identifier: "device__location",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "type__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 100000,
      },
      {
        id: "f94e10b6-9935-4f40-aa32-ac74ef62ebf3",
        name: "status",
        peer: "Status",
        kind: "Attribute",
        label: "Status",
        description: null,
        identifier: "device__status",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "label__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 101000,
      },
      {
        id: "846cee9b-e0e4-42ae-a0df-1664e78cfdd8",
        name: "role",
        peer: "Role",
        kind: "Attribute",
        label: "Role",
        description: null,
        identifier: "device__role",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "label__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 102000,
      },
      {
        id: "c82cb8c2-7257-4071-b2dc-86a19121af5b",
        name: "interfaces",
        peer: "Interface",
        kind: "Component",
        label: "Interfaces",
        description: null,
        identifier: "device__interface",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "speed__value",
            kind: "Number",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "mtu__value",
            kind: "Number",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "enabled__value",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 103000,
      },
      {
        id: "b8105b11-3f01-4cd3-95e1-67bec30ad6e4",
        name: "asn",
        peer: "AutonomousSystem",
        kind: "Attribute",
        label: "Asn",
        description: null,
        identifier: "autonomoussystem__device",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: true,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "asn__value",
            kind: "Number",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 104000,
      },
      {
        id: "09021e76-7966-4258-850d-edd4dca39ba1",
        name: "tags",
        peer: "Tag",
        kind: "Attribute",
        label: "Tags",
        description: null,
        identifier: "device__tag",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        order_weight: 105000,
      },
    ],
    label: "Device",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [
      {
        name: "ids",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        name: "name__value",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        name: "description__value",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        name: "type__value",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        name: "site__id",
        kind: "Object",
        enum: null,
        object_kind: "Location",
        description: null,
      },
      {
        name: "status__id",
        kind: "Object",
        enum: null,
        object_kind: "Status",
        description: null,
      },
      {
        name: "role__id",
        kind: "Object",
        enum: null,
        object_kind: "Role",
        description: null,
      },
      {
        name: "asn__id",
        kind: "Object",
        enum: null,
        object_kind: "AutonomousSystem",
        description: null,
      },
      {
        name: "tags__id",
        kind: "Object",
        enum: null,
        object_kind: "Tag",
        description: null,
      },
    ],
  },
];

export const deviceDetailsMocksQuery = `
query  {
  device (ids: ["${deviceDetailsMocksId}"]) {
    edges {
      node {
        id
        display_label
          name {
              value
              updated_at
              is_protected
              is_visible
              source {
                id
                display_label
                __typename
              }
              owner {
                id
                display_label
                __typename
              }
          }
          description {
              value
              updated_at
              is_protected
              is_visible
              source {
                id
                display_label
                __typename
              }
              owner {
                id
                display_label
                __typename
              }
          }
          type {
              value
              updated_at
              is_protected
              is_visible
              source {
                id
                display_label
                __typename
              }
              owner {
                id
                display_label
                __typename
              }
          }
            site {
                node {
                  id
                  display_label
                  __typename
                }
                properties {
                  updated_at
                  is_protected
                  is_visible
                  source {
                    id
                    display_label
                    __typename
                  }
                  owner {
                    id
                    display_label
                    __typename
                  }
                  __typename
                }
            }
            status {
                node {
                  id
                  display_label
                  __typename
                }
                properties {
                  updated_at
                  is_protected
                  is_visible
                  source {
                    id
                    display_label
                    __typename
                  }
                  owner {
                    id
                    display_label
                    __typename
                  }
                  __typename
                }
            }
            role {
                node {
                  id
                  display_label
                  __typename
                }
                properties {
                  updated_at
                  is_protected
                  is_visible
                  source {
                    id
                    display_label
                    __typename
                  }
                  owner {
                    id
                    display_label
                    __typename
                  }
                  __typename
                }
            }
            asn {
                node {
                  id
                  display_label
                  __typename
                }
                properties {
                  updated_at
                  is_protected
                  is_visible
                  source {
                    id
                    display_label
                    __typename
                  }
                  owner {
                    id
                    display_label
                    __typename
                  }
                  __typename
                }
            }
            tags(limit: 100) {
                edges {
                node {
                  id
                  display_label
                  __typename
                }
                properties {
                  updated_at
                  is_protected
                  is_visible
                  source {
                    id
                    display_label
                    __typename
                  }
                  owner {
                    id
                    display_label
                    __typename
                  }
                  __typename
                }
              }
          }
      }
    }
  }
}
`;

export const deviceDetailsMocksData = {
  device: {
    edges: [
      {
        node: {
          id: deviceDetailsMocksId,
          display_label: "atl1-edge1",
          name: {
            value: "atl1-edge1",
            updated_at: "2023-06-01T11:58:12.267670+00:00",
            is_protected: true,
            is_visible: true,
            source: {
              id: "79058b7b-8f2f-4561-b455-044390273707",
              display_label: "Pop-Builder",
              __typename: "Account",
            },
            owner: null,
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            updated_at: "2023-06-01T11:58:12.267670+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          type: {
            value: "7280R3",
            updated_at: "2023-06-01T11:58:12.267670+00:00",
            is_protected: false,
            is_visible: true,
            source: {
              id: "79058b7b-8f2f-4561-b455-044390273707",
              display_label: "Pop-Builder",
              __typename: "Account",
            },
            owner: null,
            __typename: "TextAttribute",
          },
          site: {
            node: {
              id: "784bd1f3-fe34-453e-9f97-70126cc55d9a",
              display_label: "atl1",
              __typename: "Location",
            },
            properties: {
              updated_at: "2023-06-01T11:58:12.267670+00:00",
              source: {
                id: "79058b7b-8f2f-4561-b455-044390273707",
                display_label: "Pop-Builder",
                __typename: "Account",
              },
              owner: null,
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedLocation",
          },
          status: {
            node: {
              id: "8f277100-5750-4b7c-81ae-5983ef73c488",
              display_label: "Active",
              __typename: "Status",
            },
            properties: {
              updated_at: "2023-06-01T11:58:12.267670+00:00",
              source: null,
              owner: {
                id: "9955e083-0be9-4cdb-98bb-d80b3e8bb4af",
                display_label: "Operation Team",
                __typename: "Group",
              },
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedStatus",
          },
          role: {
            node: {
              id: "941620c3-8b41-4f47-af92-e7e003296e28",
              display_label: "Edge",
              __typename: "Role",
            },
            properties: {
              updated_at: "2023-06-01T11:58:12.267670+00:00",
              source: {
                id: "79058b7b-8f2f-4561-b455-044390273707",
                display_label: "Pop-Builder",
                __typename: "Account",
              },
              owner: {
                id: "e07c3c38-e0de-4328-ae87-a555b90813de",
                display_label: deviceDetailsMocksOwnerName,
                __typename: "Group",
              },
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedRole",
          },
          asn: {
            node: {
              id: "b6a894e3-1343-4bc0-8a84-b96c451da038",
              display_label: deviceDetailsMocksASNName,
              __typename: "AutonomousSystem",
            },
            properties: {
              updated_at: "2023-06-01T11:58:12.267670+00:00",
              source: {
                id: "79058b7b-8f2f-4561-b455-044390273707",
                display_label: "Pop-Builder",
                __typename: "Account",
              },
              owner: {
                id: "e07c3c38-e0de-4328-ae87-a555b90813de",
                display_label: deviceDetailsMocksOwnerName,
                __typename: "Group",
              },
              __typename: "RelationshipProperty",
            },
            __typename: "NestedEdgedAutonomousSystem",
          },
          tags: {
            edges: [
              {
                node: {
                  id: "1fb11cbc-648d-40f3-83a0-8f96ed859518",
                  display_label: deviceDetailsMocksTagName,
                  __typename: "Tag",
                },
                properties: {
                  updated_at: "2023-06-01T11:58:12.267670+00:00",
                  source: null,
                  owner: null,
                  __typename: "RelationshipProperty",
                },
                __typename: "NestedEdgedTag",
              },
              {
                node: {
                  id: "26e50a37-a3f1-40b7-9509-fd4b286d72d7",
                  display_label: "red",
                  __typename: "Tag",
                },
                properties: {
                  updated_at: "2023-06-01T11:58:12.267670+00:00",
                  source: null,
                  owner: null,
                  __typename: "RelationshipProperty",
                },
                __typename: "NestedEdgedTag",
              },
            ],
            __typename: "NestedPaginatedTag",
          },
          __typename: "Device",
        },
        __typename: "EdgedDevice",
      },
    ],
    __typename: "PaginatedDevice",
  },
};
