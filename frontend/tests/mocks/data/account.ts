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
  {
    id: "17d1210a-e409-9fee-33ff-c514c1a714c1",
    state: "present",
    name: "Tag",
    namespace: "Builtin",
    description: "Standard Tag object to attached to other objects to provide some context.",
    label: "Tag",
    branch: "aware",
    default_filter: "name__value",
    human_friendly_id: null,
    display_labels: ["name__value"],
    include_in_menu: true,
    menu_placement: null,
    icon: "mdi:tag-multiple",
    order_by: ["name__value"],
    uniqueness_constraints: null,
    documentation: null,
    filters: [
      {
        id: null,
        state: "present",
        name: "ids",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "name__value",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "name__values",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "name__is_visible",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "name__is_protected",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "name__source__id",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "name__owner__id",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "description__value",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "description__values",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "description__is_visible",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "description__is_protected",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "description__source__id",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "description__owner__id",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "any__value",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "any__is_visible",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "any__is_protected",
        kind: "Boolean",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "any__source__id",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
      {
        id: null,
        state: "present",
        name: "any__owner__id",
        kind: "Text",
        enum: null,
        object_kind: null,
        description: null,
      },
    ],
    attributes: [
      {
        id: "17d1210a-e4b6-98b1-33f0-c51e93b6a148",
        state: "present",
        name: "name",
        kind: "Text",
        enum: null,
        choices: null,
        regex: null,
        max_length: null,
        min_length: null,
        label: "Name",
        description: null,
        read_only: false,
        unique: true,
        optional: false,
        branch: "aware",
        order_weight: 1000,
        default_value: null,
        inherited: false,
        allow_override: "any",
      },
      {
        id: "17d1210a-e55e-bfbb-33f3-c51195e6c6cd",
        state: "present",
        name: "description",
        kind: "Text",
        enum: null,
        choices: null,
        regex: null,
        max_length: null,
        min_length: null,
        label: "Description",
        description: null,
        read_only: false,
        unique: false,
        optional: true,
        branch: "aware",
        order_weight: 2000,
        default_value: null,
        inherited: false,
        allow_override: "any",
      },
    ],
    relationships: [
      {
        id: "17d1210a-e615-ef66-33f3-c51dedac49a2",
        state: "present",
        name: "member_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Member Of Groups",
        description: null,
        identifier: "group_member",
        cardinality: "many",
        min_count: 0,
        max_count: 0,
        order_weight: 3000,
        optional: true,
        branch: "aware",
        inherited: false,
        direction: "bidirectional",
        hierarchical: null,
        filters: [
          {
            id: null,
            state: "present",
            name: "ids",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        on_delete: "no-action",
        allow_override: "any",
        read_only: false,
      },
      {
        id: "17d1210a-e6bc-73fb-33f7-c5129b5628d9",
        state: "present",
        name: "subscriber_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Subscriber Of Groups",
        description: null,
        identifier: "group_subscriber",
        cardinality: "many",
        min_count: 0,
        max_count: 0,
        order_weight: 4000,
        optional: true,
        branch: "aware",
        inherited: false,
        direction: "bidirectional",
        hierarchical: null,
        filters: [
          {
            id: null,
            state: "present",
            name: "ids",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "name__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "label__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        on_delete: "no-action",
        allow_override: "any",
        read_only: false,
      },
      {
        id: "17d1210a-e778-c909-33f0-c51eac8c1283",
        state: "present",
        name: "profiles",
        peer: "ProfileBuiltinTag",
        kind: "Profile",
        label: "Profiles",
        description: null,
        identifier: "node__profile",
        cardinality: "many",
        min_count: 0,
        max_count: 0,
        order_weight: 5000,
        optional: true,
        branch: "aware",
        inherited: false,
        direction: "bidirectional",
        hierarchical: null,
        filters: [
          {
            id: null,
            state: "present",
            name: "ids",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_name__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_name__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_name__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_name__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_name__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_name__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_priority__value",
            kind: "Number",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_priority__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_priority__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_priority__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_priority__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "profile_priority__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__value",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__values",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__is_visible",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__is_protected",
            kind: "Boolean",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__source__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
          {
            id: null,
            state: "present",
            name: "description__owner__id",
            kind: "Text",
            enum: null,
            object_kind: null,
            description: null,
          },
        ],
        on_delete: "no-action",
        allow_override: "any",
        read_only: false,
      },
    ],
    inherit_from: [],
    hierarchy: null,
    parent: null,
    children: null,
    kind: "BuiltinTag",
    hash: "b267d6903fd80597c43a5b5291e53bef",
  },
];

export const accountDetailsMocksQuery = `query CoreAccount {
  CoreAccount (ids: ["${accountId}"] ) {
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
