import Handlebars from "handlebars";

export const getTaskItemDetails = Handlebars.compile(`
query GetTaskDetails {
  {{kind}}(ids: ["{{id}}"]) {
    count
    edges {
      node {
        created_at
        id
        related_node
        related_node_kind
        title
        updated_at
        state
        progress
        logs {
          edges {
            node {
              id
              message
              severity
              timestamp
            }
          }
        }
      }
    }
  }
}
`);
