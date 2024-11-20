import Handlebars from "handlebars";

export const getTasksItems = Handlebars.compile(`
query GET_TASKS($offset: Int, $limit: Int, $search: String, $branch: String, $state: [StateType]) {
  {{kind}}(
    offset: $offset
    limit: $limit
    q: $search
    branch: $branch
    state: $state
    {{#if relatedNode}}related_node__ids: ["{{relatedNode}}"]{{/if}}
  ) {
    count
    edges {
      node {
        created_at
        id
        branch
        related_node
        related_node_kind
        title
        updated_at
        state
        progress
        workflow
      }
    }
  }
}
`);
