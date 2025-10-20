import type { Branch } from "@/shared/api/graphql/generated/graphql";

import {
  type CreateBranchFromApiParams,
  createBranchFromApi,
} from "@/entities/branches/api/create-branch-from-api";

export type CreateBranchParams = CreateBranchFromApiParams;
export type CreateBranch = (params: CreateBranchParams) => Promise<Branch | null>;

export const createBranch: CreateBranch = async (params) => {
  const { data, errors } = await createBranchFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data?.BranchCreate?.object ?? null;
};
