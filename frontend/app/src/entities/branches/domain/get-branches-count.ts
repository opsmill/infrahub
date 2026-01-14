import type { Filter } from "@/shared/hooks/useFilters";

import { getBranchesCountFromApi } from "@/entities/branches/api/get-branches-count-from-api";
import {
  getNameFilterValue,
  type InfrahubBranchResponse,
} from "@/entities/branches/domain/branch.mappers";

export const getBranchesCount = async (filters?: Filter[]): Promise<number> => {
  const nameValue = getNameFilterValue(filters);
  const { data, errors } = await getBranchesCountFromApi({
    nameValue,
    partialMatch: nameValue ? true : undefined,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  return response?.InfrahubBranch?.count ?? 0;
};
