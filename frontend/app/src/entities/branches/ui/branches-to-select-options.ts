import type { BranchListItem } from "@/entities/branches/domain/model/branch";

export const branchesToSelectOptions = (branches: BranchListItem[]) =>
  branches
    .map((branch) => ({
      id: branch.name,
      name: branch.name,
      status: branch.status,
      sync_with_git: branch.sync_with_git,
      is_default: branch.is_default,
      schema_differs_from_default_branch: branch.schema_differs_from_default_branch,
      created_at: branch.created_at,
    }))
    .sort((a, b) => {
      // The default branch always pins to the top.
      if (a.is_default) return -1;
      if (b.is_default) return 1;
      return a.name.localeCompare(b.name);
    });
