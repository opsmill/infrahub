import { graphql } from "gql.tada";

export const GET_TASK_DETAILS_TITLE = graphql(`
  query GET_TASK_DETAILS_TITLE($ids: [String!]) {
    InfrahubTask(ids: $ids) {
      count
      edges {
        node {
          title
        }
      }
    }
  }
`);
