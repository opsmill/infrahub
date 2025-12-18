import {
  type CreateBranchFromApiParams,
  createBranchFromApi,
} from "@/entities/branches/api/create-branch-from-api";

export type CreateBranchParams = CreateBranchFromApiParams;

export const createBranch = async (params: CreateBranchParams) => {
  const { data, errors } = await createBranchFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data?.BranchCreate?.object ?? null;
};
