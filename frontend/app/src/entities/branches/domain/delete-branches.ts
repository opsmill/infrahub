import { deleteBranchesFromApi } from "@/entities/branches/api/delete-branches-from-api";

export type DeleteBranchesParams = {
  names: string[];
};

export type DeleteBranchesResult = {
  deleted: string[];
  failed: string[];
};

export type DeleteBranches = (params: DeleteBranchesParams) => Promise<DeleteBranchesResult>;

export const deleteBranches: DeleteBranches = async ({ names }) => {
  return deleteBranchesFromApi({ names });
};
