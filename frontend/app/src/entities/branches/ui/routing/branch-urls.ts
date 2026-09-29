import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

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

export function withBranch(path: string, branchName: string, isDefault: boolean): string {
  if (isDefault) return constructPath(path, [{ name: QSP.BRANCH, exclude: true }]);
  return constructPath(path, [{ name: QSP.BRANCH, value: branchName }]);
}
