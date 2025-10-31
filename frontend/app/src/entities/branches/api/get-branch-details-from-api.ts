import type {
  Get_Branch_DetailsQuery,
  Get_Branch_DetailsQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

import { GET_BRANCHES } from "@/entities/branches/api/query/get-branches-query";

export interface GetBranchDetailsFromApiParams extends BranchContextParams {}

export function getBranchDetailsFromApi({ branchName }: GetBranchDetailsFromApiParams) {
  return graphqlClient.query<Get_Branch_DetailsQuery, Get_Branch_DetailsQueryVariables>({
    query: GET_BRANCHES,
    variables: { branchName },
  });
}
