export const accountDetailsMocksQuery = `query  {
      account (ids: ["1234"]) {
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
      }
    }
  }
}
`;
