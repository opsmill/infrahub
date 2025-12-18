import {
  type GetBranchDetailsFromApiParams,
  getBranchDetailsFromApi,
} from "@/entities/branches/api/get-branch-details-from-api";
import {
  type BranchDetail,
  type InfrahubBranchResponse,
  mapToBranchDetail,
} from "@/entities/branches/domain/branch.mappers";

export type GetBranchDetailsParams = GetBranchDetailsFromApiParams;

export type GetBranchDetailsResult = BranchDetail;

export type GetBranchDetails = (params: GetBranchDetailsParams) => Promise<GetBranchDetailsResult>;

export const getBranchDetails: GetBranchDetails = async (params) => {
  const { data, errors } = await getBranchDetailsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  const result = response?.InfrahubBranch?.edges[0];

  if (!result?.node) throw new Error(`Branch ${params.branchName} not found`);

  return mapToBranchDetail(result.node);
};
