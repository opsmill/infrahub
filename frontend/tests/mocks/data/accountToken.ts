import { iNodeSchema } from "../../../src/state/atoms/schema.atom";

export const accountTokenId = "bfb5c658-d606-47b1-b614-d2e44e6d3e67";

export const accountTokenDetailsMocksSchema: iNodeSchema[] = [
  {
    id: accountTokenId,
    name: "AccountToken",
    namespace: "Internal",
    description: "Token for User Account",
    default_filter: "token__value",
    order_by: undefined,
    display_labels: ["token__value"],
    attributes: [
      {
        id: "a860d35c-76e0-4e07-a76c-ce36948a6464",
        name: "name",
        kind: "Text",
        namespace: "Attribute",
        label: "Name",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 1000,
      },
      {
        id: "dc040126-b39b-4522-a147-9cbd138f4464",
        name: "token",
        kind: "Text",
        namespace: "Attribute",
        label: "Token",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: true,
        branch: true,
        optional: false,
        order_weight: 2000,
      },
      {
        id: "5f156988-5e99-4dff-b3ee-30120a95d344",
        name: "expiration",
        kind: "DateTime",
        namespace: "Attribute",
        label: "Expiration",
        description: undefined,
        default_value: undefined,
        enum: undefined,
        regex: undefined,
        max_length: undefined,
        min_length: undefined,
        inherited: false,
        unique: false,
        branch: true,
        optional: true,
        order_weight: 3000,
      },
    ],
    relationships: [
      {
        id: "8ed7a95f-5b49-4df4-b901-c8cd1d9e6430",
        name: "account",
        peer: "CoreAccount",
        kind: "Generic",
        label: "Account",
        description: undefined,
        identifier: "coreaccount__internalaccounttoken",
        inherited: false,
        cardinality: "one",
        branch: true,
        optional: false,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "label__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "type__value",
            kind: "Text",
            enum: ["User", "Script", "Bot", "Git"],
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "role__value",
            kind: "Text",
            enum: ["admin", "read-only", "read-write"],
            object_kind: undefined,
            description: undefined,
          },
        ],
        order_weight: 4000,
      },
      {
        id: "78a226e0-7670-4e6b-aac1-77aacfb406d0",
        name: "member_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Member Of Groups",
        description: undefined,
        identifier: "group_member",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "label__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
        ],
        order_weight: 5000,
      },
      {
        id: "ee77fcc3-d6fc-4091-a17f-739c3039795f",
        name: "subscriber_of_groups",
        peer: "CoreGroup",
        kind: "Group",
        label: "Subscriber Of Groups",
        description: undefined,
        identifier: "group_subscriber",
        inherited: false,
        cardinality: "many",
        branch: true,
        optional: true,
        filters: [
          {
            name: "id",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "name__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "label__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
          {
            name: "description__value",
            kind: "Text",
            enum: undefined,
            object_kind: undefined,
            description: undefined,
          },
        ],
        order_weight: 6000,
      },
    ],
    label: "Account Token",
    inherit_from: [],
    groups: [],
    branch: true,
    filters: [
      {
        name: "ids",
        kind: "Text",
        enum: undefined,
        object_kind: undefined,
        description: undefined,
      },
      {
        name: "name__value",
        kind: "Text",
        enum: undefined,
        object_kind: undefined,
        description: undefined,
      },
      {
        name: "token__value",
        kind: "Text",
        enum: undefined,
        object_kind: undefined,
        description: undefined,
      },
    ],
    kind: "InternalAccountToken",
  },
];

export const accountTokenDetailsMocksQuery = "";

export const accountTokenDetailsMocksData = {
  CoreAccount: {
    edges: [
      {
        node: {
          id: accountTokenId,
          display_label: "06438eb2-8019-4776-878c-0941b1f1d1ec",
          name: {
            value: undefined,
            updated_at: "2023-07-11T11:58:15.601946+00:00",
            is_protected: false,
            is_visible: true,
            source: undefined,
            owner: undefined,
            __typename: "TextAttribute",
          },
          token: {
            value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
            updated_at: "2023-07-11T11:58:15.601946+00:00",
            is_protected: false,
            is_visible: true,
            source: undefined,
            owner: undefined,
            __typename: "TextAttribute",
          },
          expiration: {
            value: "2023-07-14T22:00:00.000Z",
            updated_at: "2023-07-11T14:21:05.766478+00:00",
            is_protected: false,
            is_visible: true,
            source: undefined,
            owner: undefined,
            __typename: "TextAttribute",
          },
          __typename: "InternalAccountToken",
        },
      },
    ],
    __typename: "PaginatedCoreAccount",
  },
};

export const accountTokenFormStructure = [
  {
    name: "name.value",
    kind: "Text",
    type: "text",
    label: "Name",
    value: undefined,
    options: { values: [] },
    config: { required: "" },
    isProtected: false,
  },
  {
    name: "token.value",
    kind: "Text",
    type: "text",
    label: "Token",
    value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
    options: { values: [] },
    config: { required: "Required" },
    isProtected: false,
  },
  {
    name: "expiration.value",
    kind: "DateTime",
    type: "datepicker",
    label: "Expiration",
    value: "2023-07-14T22:00:00.000Z",
    options: { values: [] },
    config: { required: "" },
    isProtected: false,
  },
  {
    name: "account.id",
    kind: "String",
    type: "select",
    label: "Account",
    value: "",
    options: { values: [] },
    config: { required: "Required" },
    isProtected: false,
  },
];

export const accountTokenDetailsUpdateDataMocksData = {
  name: { value: "New name" },
  token: { value: "06438eb2-8019-4776-878c-0941b1f1d1ec" },
  expiration: { value: "2023-07-15T22:00:00.000Z" },
  account: { id: "95b04b43-91de-4e29-844d-5655abe696b5" },
};

export const accountTokenDetailsUpdatesMocksData = {
  name: { value: "New name" },
  expiration: { value: "2023-07-15T22:00:00.000Z" },
  account: { id: "95b04b43-91de-4e29-844d-5655abe696b5" },
};

export const accountTokenMutationMocksData = `
mutation InternalAccountTokenUpdate {
  InternalAccountTokenUpdate (data: {
    id: "${accountTokenId}",
    name: {
        value: "New name"
    },
    expiration: {
        value: "2023-07-15T22:00:00.000Z"
    },
    account: {
        id: "95b04b43-91de-4e29-844d-5655abe696b5"
    }
}) {
      ok
  }
}
`;
