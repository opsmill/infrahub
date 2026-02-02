import { apiClient } from "@/shared/api/rest/client";

export type GetArtifactsDiffFromApiParams = {
  branch: string;
};

export async function getArtifactsDiffFromApi({ branch }: GetArtifactsDiffFromApiParams) {
  return apiClient.GET("/api/diff/artifacts", {
    params: { query: { branch } },
  });
}
