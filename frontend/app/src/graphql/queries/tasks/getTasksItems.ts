import { gql } from "@apollo/client";

export const GET_TASKS = gql`
query GET_TASKS($offset: Int, $limit: Int, $search: String, $branch: String, $state: [StateType], $relatedNode: [String]) {
  InfrahubTask(
    offset: $offset
    limit: $limit
    q: $search
    branch: $branch
    state: $state
    related_node__ids: $relatedNode
  ) {
    count
    edges {
      node {
        created_at
        id
        branch
        related_node
        related_nodes {
          id
          kind
        }
        title
        updated_at
        state
        progress
        workflow
      }
    }
  }
}
`;
