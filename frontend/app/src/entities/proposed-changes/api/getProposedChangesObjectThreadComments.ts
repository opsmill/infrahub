import Handlebars from "handlebars";

export const getProposedChangesObjectThreadComments = Handlebars.compile(`
query getProposedChangesObjectThreadCommentsFor{{kind}}{
  {{kind}}(
    change__ids: "{{id}}"
    object_path__value: "{{path}}"
  ) {
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
}
`);
