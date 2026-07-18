import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";

export type BranchDetailsTab = "data" | "files" | "artifacts" | "schema";

export function getBranchDetailsUrl(
  branchName: string,
  tab?: BranchDetailsTab,
  overrideParams?: overrideQueryParams[]
): string {
  // Encode the branch name so a `/` in it (e.g. "feature/my-branch") stays inside
  // a single path segment and is not parsed as a separator by the `:branchName`
  // route. React Router decodes the param again when reading it via useParams.
  const encodedBranchName = encodeURIComponent(branchName);
  const path = tab ? `/branches/${encodedBranchName}/${tab}` : `/branches/${encodedBranchName}`;
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
    .sort((a, b) => {
      // "main" always pins to the top.
      if (a.name === "main") return -1;
      if (b.name === "main") return 1;
      return a.name.localeCompare(b.name);
    });
