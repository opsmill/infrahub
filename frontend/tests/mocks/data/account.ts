export const accountId = "bfb5c658-d606-47b1-b614-d2e44e6d3e67";

export const accountDetailsMocksSchema = [
  {
    id: "04877c42-780a-4622-aa2f-7838952c5d93",
    name: "Account",
    namespace: "Core",
    description: null,
    default_filter: "name__value",
    order_by: ["name__value"],
    display_labels: ["label__value"],
    attributes: [
      {
        id: "91b7bafa-8f42-43b4-9f62-3f79aaa03144",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
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
        id: "a1816764-8b04-4596-aa5c-49abda0d27bb",
        name: "password",
        kind: "HashedPassword",
        namespace: "Attribute",
        label: "Password",
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
        order_weight: 2000,
      },
      {
        id: "bced0093-02b8-4102-b9e0-05996fcfbceb",
        name: "label",
        kind: "Text",
        namespace: "Attribute",
        label: "Label",
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
        order_weight: 3000,
      },
      {
        id: "4810c0cd-5715-43ad-873a-96f9a5840b06",
        name: "description",
        kind: "Text",
        namespace: "Attribute",
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
        order_weight: 4000,
      },
      {
        id: "bd65010c-b088-42fd-b9f3-e43de03641af",
        name: "type",
        kind: "Text",
        namespace: "Attribute",
        label: "Type",
        description: null,
        default_value: "User",
        enum: ["User", "Script", "Bot", "Git"],
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 5000,
      },
      {
        id: "fa8468e3-015a-4fcb-b1e1-0a6e968376e3",
        name: "role",
        kind: "Text",
        namespace: "Attribute",
        label: "Role",
        description: null,
        default_value: "read-only",
        enum: ["admin", "read-only", "read-write"],
        regex: null,
        max_length: null,
        min_length: null,
        inherited: false,
        unique: false,
        branch: true,
        optional: false,
        order_weight: 6000,
      },
    ],
    relationships: [
      {
        id: "66425709-f212-4ca6-b908-80171562a310",
        name: "tokens",
        peer: "InternalAccountToken",
        kind: "Generic",
        label: "Tokens",
        description: null,
        identifier: "coreaccount__internalaccounttoken",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          { name: "id", kind: "Text", enum: null, object_kind: null, description: null },
          { name: "token__value", kind: "Text", enum: null, object_kind: null, description: null },
        ],
        order_weight: 7000,
      },
    ],
    label: "Account",
    inherit_from: ["LineageOwner", "LineageSource"],
    groups: [],
    branch: true,
    filters: [
      { name: "ids", kind: "Text", enum: null, object_kind: null, description: null },
      { name: "name__value", kind: "Text", enum: null, object_kind: null, description: null },
      { name: "label__value", kind: "Text", enum: null, object_kind: null, description: null },
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
        enum: ["User", "Script", "Bot", "Git"],
        object_kind: null,
        description: null,
      },
      {
        name: "role__value",
        kind: "Text",
        enum: ["admin", "read-only", "read-write"],
        object_kind: null,
        description: null,
      },
    ],
    kind: "CoreAccount",
  },
];

export const accountDetailsMocksQuery = `query CoreAccount {
  CoreAccount (ids: ["${accountId}"]) {
    edges {
      node {
        id
        display_label
        profiles {
          edges {
            node {
              display_label
              id
            }
          }
        }
        name {
            value
            updated_at
            is_from_profile
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
        label {
            value
            updated_at
            is_from_profile
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
            is_from_profile
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
            is_from_profile
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
        role {
            value
            updated_at
            is_from_profile
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
      }
    }
  }
}
`;

export const accountDetailsMocksData = {
  CoreAccount: {
    edges: [
      {
        node: {
          id: accountId,
          display_label: "Admin",
          name: {
            value: "admin",
            updated_at: "2023-07-03T06:51:06.645925+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          password: {
            value: "$2b$12$9/3ivk9fIDWah40iXsCn1ubiwkCKNIuyOlUww1wVJ6CuQ2Q2u8wAS",
            updated_at: "2023-07-03T06:51:06.645925+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          label: {
            value: "Admin",
            updated_at: "2023-07-03T06:51:06.645925+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          description: {
            value: null,
            updated_at: "2023-07-03T06:51:06.645925+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          type: {
            value: "User",
            updated_at: "2023-07-03T06:51:06.645925+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          role: {
            value: "admin",
            updated_at: "2023-07-03T06:51:06.645925+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
    ],
    __typename: "PaginatedCoreAccount",
  },
};
