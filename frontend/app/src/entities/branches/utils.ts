import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";

export type BranchDetailsTab = "data" | "files" | "artifacts" | "schema";

export function getBranchDetailsUrl(
  branchName: string,
  tab?: BranchDetailsTab,
  overrideParams?: overrideQueryParams[]
): string {
  const path = tab ? `/branches/${branchName}/${tab}` : `/branches/${branchName}`;
  return constructPath(path, overrideParams);
}

export const findSelectedBranch = (
  branches: BranchListItem[],
  branchName?: string | null
): BranchListItem | null => {
  const filter = branchName
    ? (b: BranchListItem) => branchName === b.name
    : (b: BranchListItem) => b.is_default;

  return branches.find(filter) ?? null;
};

export const branchesToSelectOptions = (branches: BranchListItem[]) =>
  branches
    .map((branch) => ({
      id: branch.name,
      name: branch.name,
      status: branch.status,
      sync_with_git: branch.sync_with_git,
      is_default: branch.is_default,
      has_schema_changes: branch.has_schema_changes,
      created_at: branch.created_at,
    }))
    .sort((branch1, branch2) => {
      if (branch1.name === "main") {
        return -1;
      }

      if (branch2.name === "main") {
        return 1;
      }

      if (branch2.name === "main") {
        return -1;
      }

      if (branch1.name > branch2.name) {
        return 1;
      }

      return -1;
    });
