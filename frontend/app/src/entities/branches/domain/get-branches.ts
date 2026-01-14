import type { Filter } from "@/shared/hooks/useFilters";
import { store } from "@/shared/stores";

import type { PaginationParams } from "@/shared/api/types";

import { getBranchesFromApi } from "@/entities/branches/api/get-branches-from-api";
import {
  type BranchListItem,
  type InfrahubBranchResponse,
  mapToBranchListItem,
} from "@/entities/branches/domain/branch.mappers";
import { branchesState } from "@/entities/branches/stores";

export type GetBranchesParams = PaginationParams & {
  filters?: Filter[];
};

export type GetBranchesResult = Array<BranchListItem>;

export type GetBranches = (params?: GetBranchesParams) => Promise<GetBranchesResult>;

const getNameFilterValue = (filters?: Filter[]) => {
  const nameFilter = filters?.find((f) => f.name === "name__value");
  return nameFilter?.value as string | undefined;
};

// Paginated fetch for branches list view
export const getBranches: GetBranches = async (params = {}) => {
  const nameValue = getNameFilterValue(params.filters);
  const { data, errors } = await getBranchesFromApi({
    limit: params.limit,
    offset: params.offset,
    nameValue,
    partialMatch: nameValue ? true : undefined,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  const branches = response?.InfrahubBranch?.edges.map((edge) => mapToBranchListItem(edge)) ?? [];

  return branches;
};

// Fetch all branches without pagination (for branch selector and provider)
export const getAllBranches = async (): Promise<GetBranchesResult> => {
  const { data, errors } = await getBranchesFromApi({ limit: undefined });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  const branches =
    response?.InfrahubBranch?.edges.map(({ node, node_metadata }) =>
      mapToBranchListItem({ node, node_metadata })
    ) ?? [];

  store.set(branchesState, branches);

  return branches;
};
