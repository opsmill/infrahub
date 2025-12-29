import type {
  GetBranchDetailsQuery,
  GetBranchDetailsQueryVariables,
} from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";

import { GET_BRANCH_DETAILS } from "@/entities/branches/api/get-branch-details-query";

export interface GetBranchDetailsFromApiParams extends BranchContextParams {}

export function getBranchDetailsFromApi({ branchName }: GetBranchDetailsFromApiParams) {
  return graphqlClient.query<GetBranchDetailsQuery, GetBranchDetailsQueryVariables>({
    query: GET_BRANCH_DETAILS,
    variables: { branchName },
  });
}
