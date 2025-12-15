import { getBranchesCountFromApi } from "@/entities/branches/api/get-branches-count-from-api";
import type { InfrahubBranchResponse } from "@/entities/branches/domain/branch.mappers";

// Fetch branches count (for header badge)
export const getBranchesCount = async (branchName?: string): Promise<number> => {
  const { data, errors } = await getBranchesCountFromApi(branchName);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const response = data as InfrahubBranchResponse;
  return response?.InfrahubBranch?.count ?? 0;
};
