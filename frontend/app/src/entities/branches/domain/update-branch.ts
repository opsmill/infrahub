import { updateBranchFromApi } from "@/entities/branches/api/update-branch-from-api";

export type UpdateBranchParams = {
  name: string;
  description: string;
};

export type UpdateBranch = (params: UpdateBranchParams) => Promise<boolean>;

export const updateBranch: UpdateBranch = async ({ name, description }) => {
  const { data, errors } = await updateBranchFromApi({ name, description });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data?.BranchUpdate?.ok ?? false;
};
