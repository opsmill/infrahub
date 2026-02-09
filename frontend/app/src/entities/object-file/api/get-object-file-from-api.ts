import { apiClient } from "@/shared/api/rest/client";

export interface GetObjectFileFromApiParams {
  nodeId: string;
  branch: string;
  parseAs?: "text" | "arrayBuffer";
}

export function getObjectFileFromApi({
  nodeId,
  branch,
  parseAs = "text",
}: GetObjectFileFromApiParams) {
  return apiClient.GET("/api/storage/files/{node_id}", {
    params: {
      path: {
        node_id: nodeId,
      },
      query: {
        branch,
        preview: true,
      },
    },
    parseAs,
  });
}
