import { apiClient } from "@/shared/api/rest/client";

export interface GetFileFromApiParams {
  repositoryId: string;
  filePath: string;
  commit?: string;
}

export async function getFileFromApi({ repositoryId, filePath, commit }: GetFileFromApiParams) {
  return apiClient.GET("/api/file/{repository_id}/{file_path}", {
    params: {
      path: { repository_id: repositoryId, file_path: filePath },
      query: { commit },
    },
    parseAs: "text",
  });
}
