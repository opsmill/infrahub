import type { InfrahubBranchResponse } from "@/entities/branches/api/branch.mappers";
import { getBranchesCountFromApi } from "@/entities/branches/api/get-branches-count-from-api";
import {
  getBranchDateFilters,
  getCreatedByFilterValue,
  getNameFilterValue,
  getStatusFilterValue,
} from "@/entities/branches/domain/rules/branch-filters";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

export const getBranchesCount = async (filters?: Filter[]): Promise<number> => {
  const nameValue = getNameFilterValue(filters);
  const statusValue = getStatusFilterValue(filters);
  const createdById = getCreatedByFilterValue(filters);
  const dateFilters = getBranchDateFilters(filters);
  const { data, errors } = await getBranchesCountFromApi({
    nameValue,
    partialMatch: nameValue ? true : undefined,
    statusValue,
    createdById,
    ...dateFilters,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  return response?.InfrahubBranch?.count ?? 0;
};
