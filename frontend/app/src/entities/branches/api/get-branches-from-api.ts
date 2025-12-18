import { GET_BRANCHES } from "@/entities/branches/api/get-branches-query";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { PaginationParams } from "@/shared/api/types";

export const BRANCHES_PER_PAGE = 40;

export interface GetBranchesFromApiParams extends PaginationParams {
	branchSearch?: string;
}

export const getBranchesFromApi = async ({
	branchSearch,
	limit = BRANCHES_PER_PAGE,
	offset,
}: GetBranchesFromApiParams = {}) => {
	return graphqlClient.query({
		query: GET_BRANCHES,
		variables: {
			branchSearch,
			limit,
			offset,
		},
	});
};
