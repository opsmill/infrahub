import Handlebars from "handlebars";

export const getProposedChangesThreads = Handlebars.compile(`query {
  {{kind}}(ids: ["{{id}}"]) {
    count
    edges {
      node {
        id
        display_label
        __typename
        _updated_at
        threads {
          count
          edges {
            node {
              __typename
              id
              display_label
              resolved {
                value
              }
              created_by {
                node {
                  display_label
                }
              }
              comments {
                count
                edges {
                  node {
                    id
                    display_label
                    created_by {
                      node {
                        display_label
                      }
                    }
                    created_at {
                      value
                    }
                    text {
                      value
                    }
                  }
                }
              }
            }
          }
        }
        comments {
          count
          edges {
            node {
              __typename
              id
              display_label
              _updated_at
              created_by {
                node {
                  display_label
                }
              }
              created_at {
                value
              }
            }
          }
        }
      }
    }
  }
}
`);
