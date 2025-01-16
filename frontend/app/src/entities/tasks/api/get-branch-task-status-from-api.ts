import { gql } from "@/shared/api/graphql/generated";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const TASKS_BRANCH_STATUS_COUNT = gql(/* GraphQL */ `
  query TASKS_BRANCH_STATUS_COUNT($branch: String!) {
    InfrahubTaskBranchStatus(branch: $branch){
      count
    }
  }
`);

export const getBranchTaskStatusFromApi = (branch: string) => {
  return graphqlClient.query({
    query: TASKS_BRANCH_STATUS_COUNT,
    variables: { branch },
  });
};
