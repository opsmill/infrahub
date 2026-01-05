import { gql } from "@apollo/client";

import type { Tasks_Branch_Status_CountQuery } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

export const TASKS_BRANCH_STATUS_COUNT = gql`
  query TASKS_BRANCH_STATUS_COUNT($branch: String!) {
    InfrahubTaskBranchStatus(branch: $branch){
      count
    }
  }
`;

export const getBranchTaskStatusFromApi = (branch: string) => {
  return graphqlClient.query<Tasks_Branch_Status_CountQuery>({
    query: TASKS_BRANCH_STATUS_COUNT,
    variables: { branch },
  });
};
