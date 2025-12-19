import {
  type CreateBranchFromApiParams,
  createBranchFromApi,
} from "@/entities/branches/api/create-branch-from-api";
import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";

export type CreateBranchParams = CreateBranchFromApiParams;

export const createBranch = async (params: CreateBranchParams): Promise<BranchListItem | null> => {
  const { data, errors } = await createBranchFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const branch = data?.BranchCreate?.object;
  if (!branch) return null;

  const now = new Date().toISOString();

  return {
    id: branch.id,
    name: branch.name,
    description: branch.description,
    branched_from: branch.branched_from,
    status: BRANCH_STATUS.OPEN,
    sync_with_git: branch.sync_with_git,
    is_default: branch.is_default,
    has_schema_changes: false,
    created_at: branch.created_at ?? now,
    updated_at: now,
    created_by: null,
  };
};
