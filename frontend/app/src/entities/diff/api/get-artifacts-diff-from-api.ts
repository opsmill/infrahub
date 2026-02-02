import { apiClient } from "@/shared/api/rest/client";

export type GetArtifactsDiffFromApiParams = {
  branch: string;
};

export async function getArtifactsDiffFromApi({ branch }: GetArtifactsDiffFromApiParams) {
  const { data, error } = await apiClient.GET("/api/diff/artifacts", {
    params: { query: { branch } },
  });

  if (error) throw error;

  return data;
}
