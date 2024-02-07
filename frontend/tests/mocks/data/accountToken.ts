import { iNodeSchema } from "../../../src/state/atoms/schema.atom";

export const accountTokenId = "bfb5c658-d606-47b1-b614-d2e44e6d3e67";
export const accountTokenNewDate = "2023-07-14T22:00:00.000Z";

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

// Same schema but with a different name to be allowed to test it even if in the MENU_EXCLUDELIST constant
export const accountTokenDetailsMocksSchemaBIS: iNodeSchema[] = [
  {
    id: accountTokenId,
    name: "AccountTokenBis",
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
    kind: "InternalAccountTokenBis",
  },
];

export const accountTokenDetailsMocksQuery = `
query InternalAccountToken {
  InternalAccountToken (ids: ["${accountTokenId}"]) {
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
          token {
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
          expiration {
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


      }
    }
  }
}
`;

export const accountTokenDetailsMocksQueryBis = `
query InternalAccountTokenBis {
  InternalAccountTokenBis (ids: ["${accountTokenId}"]) {
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
          token {
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
          expiration {
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
          account {
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
`;

export const accountTokenDetailsMocksData = {
  InternalAccountToken: {
    edges: [
      {
        node: {
          id: accountTokenId,
          display_label: "06438eb2-8019-4776-878c-0941b1f1d1ec",
          name: {
            value: null,
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          token: {
            value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          expiration: {
            value: "",
            updated_at: "2023-07-13T06:42:11.613885+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          __typename: "InternalAccountToken",
        },
        __typename: "EdgedInternalAccountToken",
      },
    ],
    __typename: "PaginatedInternalAccountToken",
  },
};

export const accountTokenDetailsMocksDataBis = {
  InternalAccountTokenBis: {
    edges: [
      {
        node: {
          id: accountTokenId,
          display_label: "06438eb2-8019-4776-878c-0941b1f1d1ec",
          name: {
            value: null,
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          token: {
            value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          expiration: {
            value: "",
            updated_at: "2023-07-13T06:42:11.613885+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          __typename: "InternalAccountTokenBis",
        },
        __typename: "EdgedInternalAccountToken",
      },
    ],
    __typename: "PaginatedInternalAccountToken",
  },
};

export const accountTokenDetailsMocksDataWithDate = {
  InternalAccountToken: {
    edges: [
      {
        node: {
          id: accountTokenId,
          display_label: "06438eb2-8019-4776-878c-0941b1f1d1ec",
          name: {
            value: null,
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          token: {
            value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          expiration: {
            value: accountTokenNewDate,
            updated_at: "2023-07-13T06:42:11.613885+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          __typename: "InternalAccountToken",
        },
        __typename: "EdgedInternalAccountToken",
      },
    ],
    __typename: "PaginatedInternalAccountToken",
  },
};

export const accountTokenDetailsMocksDataWithDateBis = {
  InternalAccountTokenBis: {
    edges: [
      {
        node: {
          id: accountTokenId,
          display_label: "06438eb2-8019-4776-878c-0941b1f1d1ec",
          name: {
            value: null,
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          token: {
            value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          expiration: {
            value: accountTokenNewDate,
            updated_at: "2023-07-13T06:42:11.613885+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          __typename: "InternalAccountTokenBis",
        },
        __typename: "EdgedInternalAccountToken",
      },
    ],
    __typename: "PaginatedInternalAccountToken",
  },
};

export const accountTokenFormStructure = [
  {
    name: "name.value",
    kind: "Text",
    type: "text",
    label: "Name",
    value: null,
    options: [],
    config: {},
    isOptional: true,
    isProtected: false,
    isReadOnly: undefined,
    isUnique: false,
  },
  {
    name: "token.value",
    kind: "Text",
    type: "text",
    label: "Token",
    value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
    options: [],
    config: {},
    isOptional: false,
    isProtected: false,
    isReadOnly: undefined,
    isUnique: true,
  },
  {
    name: "expiration.value",
    kind: "DateTime",
    type: "datepicker",
    label: "Expiration",
    value: "2023-07-14T22:00:00.000Z",
    options: [],
    config: {},
    isOptional: true,
    isProtected: false,
    isReadOnly: undefined,
    isUnique: false,
  },
  {
    name: "account.id",
    kind: "String",
    peer: "CoreAccount",
    type: "select",
    label: "Account",
    value: "",
    options: [],
    config: {},
    isOptional: true,
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

export const accountTokenMocksMutation = `
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

export const accountTokenMocksMutationBis = `
mutation InternalAccountTokenBisUpdate {
  InternalAccountTokenBisUpdate (data: {
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

export const accountTokenEditMocksQuery = `
query InternalAccountToken {
  InternalAccountToken (ids: ["${accountTokenId}"]) {
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
          token {
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
          expiration {
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
      }
    }
  }
    CoreAccount {
      edges {
        node {
          id
          display_label
        }
      }
    }
    CoreGroup {
      edges {
        node {
          id
          display_label
        }
      }
    }
    CoreGroup {
      edges {
        node {
          id
          display_label
        }
      }
    }
}
`;

export const accountTokenEditMocksQueryBis = `
query getInternalAccountTokenBisDetailsAndPeers {
  InternalAccountTokenBisDetailsAndPeers: InternalAccountTokenBis(
    ids: ["${accountTokenId}"]
  ) {
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
        token {
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
        expiration {
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
        account {
          node {
            id
            display_label
            __typename
          }
          properties {
            is_protected
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
  CoreAccount {
    edges {
      node {
        id
        display_label
      }
    }
  }
}
`;

export const accountTokenEditMocksData = {
  InternalAccountToken: {
    edges: [
      {
        node: {
          id: accountTokenId,
          display_label: "06438eb2-8019-4776-878c-0941b1f1d1ec",
          name: {
            value: null,
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          token: {
            value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          expiration: {
            value: "",
            updated_at: "2023-07-13T06:42:11.613885+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          __typename: "InternalAccountToken",
        },
        __typename: "EdgedInternalAccountToken",
      },
    ],
    __typename: "PaginatedInternalAccountToken",
  },
};

export const accountTokenEditMocksDataBis = {
  InternalAccountTokenBisDetailsAndPeers: {
    edges: [
      {
        node: {
          id: accountTokenId,
          display_label: "06438eb2-8019-4776-878c-0941b1f1d1ec",
          name: {
            value: null,
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          token: {
            value: "06438eb2-8019-4776-878c-0941b1f1d1ec",
            updated_at: "2023-07-12T15:22:03.351221+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          expiration: {
            value: "",
            updated_at: "2023-07-13T06:42:11.613885+00:00",
            is_protected: false,
            is_visible: true,
            source: null,
            owner: null,
            __typename: "TextAttribute",
          },
          __typename: "InternalAccountTokenBis",
        },
        __typename: "EdgedInternalAccountToken",
      },
    ],
    __typename: "PaginatedInternalAccountToken",
  },
};

export const accountsDropdownOptionsQuery = `
query DropdownOptions {
  CoreAccount {
    count
    edges {
      node {
        id
        display_label
        __typename
      }
    }
  }
}
`;

export const accountsDropdownOptionsData = {
  CoreAccount: {
    edges: [
      {
        node: {
          id: "c75a43b4-1df8-4d8b-894e-9fb684b62f8e",
          display_label: "Architecture Team",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "4e4ac1bf-3e5c-4c42-808e-c2fdfd684512",
          display_label: "Crm Synchronization",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "8540d34a-a525-4765-b62e-6ca746e15077",
          display_label: "Chloe O'Brian",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "68246241-9162-4156-beee-7ba4ed4563e3",
          display_label: "David Palmer",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "86cdbffb-6bb5-4fcd-808b-fd9ea020fce7",
          display_label: "Engineering Team",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "65e55704-ba5b-4876-9707-afc5d049424d",
          display_label: "Jack Bauer",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "f858c0ee-84aa-4f66-a003-2481ca1fd106",
          display_label: "Operation Team",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "d7f866a8-6b26-4c37-bd79-9082450ca16c",
          display_label: "Administrator",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
      {
        node: {
          id: "c3412415-707e-4f38-b12a-3a9814483c9f",
          display_label: "Pop-Builder",
          __typename: "CoreAccount",
        },
        __typename: "EdgedCoreAccount",
      },
    ],
    __typename: "PaginatedCoreAccount",
  },
};
