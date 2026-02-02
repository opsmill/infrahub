import { apiClient } from "@/shared/api/rest/client";

export interface GetArtifactFileFromApiParams {
  storageId: string;
}

export function getArtifactFileFromApi({ storageId }: GetArtifactFileFromApiParams) {
  return apiClient.GET("/api/storage/object/{identifier}", {
    params: {
      path: {
        identifier: storageId,
      },
    },
    parseAs: "text",
  });
}
