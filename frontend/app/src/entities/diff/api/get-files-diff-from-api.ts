import { apiClient } from "@/shared/api/rest/client";
import type { BranchContextParams } from "@/shared/api/types";

export interface GetFilesDiffFromApiParams extends BranchContextParams {}

export async function getFilesDiffFromApi({ branchName }: GetFilesDiffFromApiParams) {
  return apiClient.GET("/api/diff/files", {
    params: { query: { branch: branchName } },
  });
}
