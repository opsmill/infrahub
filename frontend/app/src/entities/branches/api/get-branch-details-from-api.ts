import type {
  GetBranchesQuery,
  GetBranchesQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

import { GET_BRANCHES } from "@/entities/branches/api/get-branches-query";

export interface GetBranchDetailsFromApiParams extends BranchContextParams {}

export function getBranchDetailsFromApi({ branchName }: GetBranchDetailsFromApiParams) {
  return graphqlClient.query<GetBranchesQuery, GetBranchesQueryVariables>({
    query: GET_BRANCHES,
    variables: { branchName },
  });
}
