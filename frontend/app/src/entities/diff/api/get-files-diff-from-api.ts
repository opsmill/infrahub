import { apiClient } from "@/shared/api/rest/client";
import type { components } from "@/shared/api/rest/types.generated";
import type { BranchContextParams } from "@/shared/api/types";

export type FileDiff = components["schemas"]["BranchDiffRepository"];
export type FileDiffFile = components["schemas"]["BranchDiffFile"];

export interface GetFilesDiffFromApiParams extends BranchContextParams {}

export async function getFilesDiffFromApi({ branchName }: GetFilesDiffFromApiParams) {
  return apiClient.GET("/api/diff/files", {
    params: { query: { branch: branchName } },
  });
}
