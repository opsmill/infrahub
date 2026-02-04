import { apiClient } from "@/shared/api/rest/client";

export interface GetObjectFileFromApiParams {
  nodeId: string;
}

export function getObjectFileFromApi({ nodeId }: GetObjectFileFromApiParams) {
  return apiClient.GET("/api/storage/files/{node_id}", {
    params: {
      path: {
        node_id: nodeId,
      },
      query: {
        preview: true,
      },
    },
    parseAs: "text",
  });
}
