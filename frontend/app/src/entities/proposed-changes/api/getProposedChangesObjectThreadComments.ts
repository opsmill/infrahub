import Handlebars from "@/shared/libs/handlebars";

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
        comments {
          count
          edges {
            node_metadata {
              created_at
              created_by {
                display_label
              }
            }
            node {
              id
              display_label
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
