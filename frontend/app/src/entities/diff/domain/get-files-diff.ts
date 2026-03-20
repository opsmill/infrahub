import type { components } from "@/shared/api/rest/types.generated";

import {
  type GetFilesDiffFromApiParams,
  getFilesDiffFromApi,
} from "@/entities/diff/api/get-files-diff-from-api";

export type FileDiff = components["schemas"]["BranchDiffRepository"];
export type FileDiffFile = components["schemas"]["BranchDiffFile"];
export type GetFilesDiffParams = GetFilesDiffFromApiParams;

export async function getFilesDiff({ branchName }: GetFilesDiffParams): Promise<FileDiff[]> {
  const { data, error } = await getFilesDiffFromApi({ branchName });

  if (error) {
    const apiError = error as { errors?: Array<{ message?: string }> };
    const message = apiError.errors?.[0]?.message;
    throw new Error(message ?? "An error occurred while fetching file diffs.");
  }

  // Response: { [branchName]: { [repoId]: BranchDiffRepository } }
  const branchData = data?.[branchName];
  if (!branchData) return [];

  return Object.values(branchData);
}
