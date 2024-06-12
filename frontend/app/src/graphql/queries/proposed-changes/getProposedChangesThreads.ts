import Handlebars from "handlebars";

export const getProposedChangesThreads = Handlebars.compile(`
query {
  {{kind}}(change__ids: "{{id}}") {
    count
    edges {
      node {
        __typename
        id
        display_label
        label {
          value
        }
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
  {{#if accountKind}}{{accountKind}}{{/if}} {
    edges {
      node {
        id
        display_label
      }
    }
  }
}
`);
