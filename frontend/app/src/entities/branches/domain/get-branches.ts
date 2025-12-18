import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { store } from "@/shared/stores";

import {
  type GetBranchesFromApiParams,
  getBranchesFromApi,
} from "@/entities/branches/api/get-branches-from-api";
import {
  type InfrahubBranchResponse,
  mapInfrahubBranchNodeToBranch,
} from "@/entities/branches/domain/branch.mappers";
import { branchesState } from "@/entities/branches/stores";

export type GetBranchesParams = GetBranchesFromApiParams;

export type GetBranchesResult = Array<Branch>;

export type GetBranches = (params?: GetBranchesParams) => Promise<GetBranchesResult>;

// Paginated fetch for branches list view
export const getBranches: GetBranches = async (params = {}) => {
  const { data, errors } = await getBranchesFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  const branches: Branch[] =
    response?.InfrahubBranch?.edges.map((edge) => mapInfrahubBranchNodeToBranch(edge)) ?? [];

  return branches;
};

// Fetch all branches without pagination (for branch selector and provider)
export const getAllBranches = async (): Promise<GetBranchesResult> => {
  const { data, errors } = await getBranchesFromApi({ limit: undefined });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  const branches: Branch[] =
    response?.InfrahubBranch?.edges.map(({ node, node_metadata }) =>
      mapInfrahubBranchNodeToBranch({ node, node_metadata })
    ) ?? [];

  store.set(branchesState, branches);

  return branches;
};
