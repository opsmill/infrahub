import type { Branch } from "@/shared/api/graphql/generated/graphql";

import {
  type GetBranchDetailsFromApiParams,
  getBranchDetailsFromApi,
} from "@/entities/branches/api/get-branch-details-from-api";
import { mapInfrahubBranchNodeToBranch } from "@/entities/branches/domain/branch.mappers";

export type GetBranchDetailsParams = GetBranchDetailsFromApiParams;

export type GetBranchDetails = (params: GetBranchDetailsParams) => Promise<Branch>;

export const getBranchDetails: GetBranchDetails = async (params) => {
  const { data, errors } = await getBranchDetailsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const branch = data?.InfrahubBranch?.edges[0]?.node;

  if (!branch) throw new Error(`Branch ${params.branchName} not found`);

  return mapInfrahubBranchNodeToBranch(branch);
};
