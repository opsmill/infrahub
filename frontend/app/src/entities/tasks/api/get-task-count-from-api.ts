import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { gql } from "@apollo/client";

const TASK_COUNT = gql`
  query TASK_COUNT($nodeIds: [String]) {
    InfrahubTask(related_node__ids: $nodeIds) {
      count
      __typename
    }
  }
`;

export function getTaskCountFromApi(nodeIds: string[]) {
  return graphqlClient.query({
    query: TASK_COUNT,
    variables: {
      nodeIds,
    },
  });
}
