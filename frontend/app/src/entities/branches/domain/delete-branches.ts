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
  const { data, errors } = await deleteBranchesFromApi({ names });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.BranchDelete?.ok) {
    return { deleted: [], failed: names };
  }

  return { deleted: names, failed: [] };
};
