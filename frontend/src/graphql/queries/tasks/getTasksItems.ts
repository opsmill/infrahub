import Handlebars from "handlebars";

export const getTasksItems = Handlebars.compile(`
query GetTasks {
  {{kind}} {
    count
    edges {
      node {
        conclusion
        created_at
        id
        related_node
        related_node_kind
        title
        updated_at
      }
    }
  }
}
`);
