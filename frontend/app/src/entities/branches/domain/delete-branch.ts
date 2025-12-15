import { deleteBranchFromApi } from "@/entities/branches/api/delete-branch-from-api";

export type DeleteBranchParams = {
  name: string;
};

export type DeleteBranch = (params: DeleteBranchParams) => Promise<string | null>;

export const deleteBranch: DeleteBranch = async ({ name }) => {
  const { data, errors } = await deleteBranchFromApi({ name });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.BranchDelete?.ok) {
    return null;
  }

  return name;
};
