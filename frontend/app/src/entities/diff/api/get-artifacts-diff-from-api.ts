import { apiClient } from "@/shared/api/rest/client";
import type { components } from "@/shared/api/rest/types.generated";

export type ArtifactDiff = components["schemas"]["BranchDiffArtifact"];

export type GetArtifactsDiffFromApiParams = {
  branch: string;
};

export async function getArtifactsDiffFromApi({ branch }: GetArtifactsDiffFromApiParams) {
  return apiClient.GET("/api/diff/artifacts", {
    params: { query: { branch } },
  });
}
