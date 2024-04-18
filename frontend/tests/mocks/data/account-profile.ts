export const profileId = "d07bb58e-8394-4053-a198-9cef84e7d6c0";

export const profileDetailsMocksQuery = `
query {
  AccountProfile {
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
      password {
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
      label {
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
      role {
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
`;

export const profileDetailsMocksData = {
  AccountProfile: {
    id: profileId,
    display_label: "Chloe O'Brian",
    name: {
      value: "Chloe O'Brian",
      updated_at: "2023-07-10T15:01:26.568139+00:00",
      is_protected: false,
      is_visible: true,
      source: null,
      owner: null,
      __typename: "TextAttribute",
    },
    password: {
      value: "$2b$12$/MIzbeLlcZZFcv9oIMPPt.yj.TT6PoSo0LVOOyRwZfNOGlEbTnlGm",
      updated_at: "2023-07-10T15:01:26.568139+00:00",
      is_protected: false,
      is_visible: true,
      source: null,
      owner: null,
      __typename: "TextAttribute",
    },
    label: {
      value: "Chloe O'Brian",
      updated_at: "2023-07-10T15:01:26.568139+00:00",
      is_protected: false,
      is_visible: true,
      source: null,
      owner: null,
      __typename: "TextAttribute",
    },
    description: {
      value: null,
      updated_at: "2023-07-10T15:01:26.568139+00:00",
      is_protected: false,
      is_visible: true,
      source: null,
      owner: null,
      __typename: "TextAttribute",
    },
    type: {
      value: "User",
      updated_at: "2023-07-10T15:01:26.568139+00:00",
      is_protected: false,
      is_visible: true,
      source: null,
      owner: null,
      __typename: "TextAttribute",
    },
    role: {
      value: "read-write",
      updated_at: "2023-07-10T15:01:26.568139+00:00",
      is_protected: false,
      is_visible: true,
      source: null,
      owner: null,
      __typename: "TextAttribute",
    },
    __typename: "CoreAccount",
  },
};
