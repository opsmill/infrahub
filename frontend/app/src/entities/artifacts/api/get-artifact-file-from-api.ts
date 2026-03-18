import { apiClient } from "@/shared/api/rest/client";

export interface GetArtifactFileFromApiParams {
  storageId: string;
  parseAs?: "text" | "arrayBuffer";
}

export function getArtifactFileFromApi({
  storageId,
  parseAs = "text",
}: GetArtifactFileFromApiParams) {
  return apiClient.GET("/api/storage/object/{identifier}", {
    params: {
      path: {
        identifier: storageId,
      },
    },
    parseAs,
  });
}
