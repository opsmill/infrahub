import { gql } from "@apollo/client";

import type {
  Get_Branch_DetailsQuery,
  Get_Branch_DetailsQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

export const getBranchDetailsQuery = gql`
  query GET_BRANCH_DETAILS($branchName: String!) {
    Branch(name: $branchName) {
      id
      name
      description
      origin_branch
      branched_from
      created_at
      sync_with_git
      is_default
    }
  }
`;

export interface GetBranchDetailsFromApiParams extends BranchContextParams {}

export function getBranchDetailsFromApi({ branchName }: GetBranchDetailsFromApiParams) {
  return graphqlClient.query<Get_Branch_DetailsQuery, Get_Branch_DetailsQueryVariables>({
    query: getBranchDetailsQuery,
    variables: { branchName },
  });
}
