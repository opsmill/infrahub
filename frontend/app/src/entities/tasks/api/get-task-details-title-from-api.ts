import { graphql, type VariablesOf } from "gql.tada";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const GET_TASK_DETAILS_TITLE = graphql(`
  query GET_TASK_DETAILS_TITLE_QUERY($ids: [String!]) {
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

export interface GetTaskDetailsTitleFromApiParams
  extends VariablesOf<typeof GET_TASK_DETAILS_TITLE> {}

export function getTaskDetailsTitleFromApi(variables: GetTaskDetailsTitleFromApiParams) {
  return graphqlClient.query({
    query: GET_TASK_DETAILS_TITLE,
    variables,
  });
}
