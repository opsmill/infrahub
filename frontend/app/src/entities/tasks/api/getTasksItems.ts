import { graphql } from "gql.tada";

export const GET_TASK_ITEMS = graphql(`
  query GET_TASK_ITEMS(
    $offset: Int
    $limit: Int
    $search: String
    $branch: String
    $state: [StateType]
    $relatedNodes: [String]
  ) {
    InfrahubTask(
      offset: $offset
      limit: $limit
      q: $search
      branch: $branch
      state: $state
      related_node__ids: $relatedNodes
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
`);
