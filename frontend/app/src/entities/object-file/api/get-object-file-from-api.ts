import { apiClient } from "@/shared/api/rest/client";
import type { ContextParams } from "@/shared/api/types";

export interface GetObjectFileFromApiParams extends ContextParams {
  nodeId: string;
  parseAs?: "text" | "arrayBuffer";
}

export function getObjectFileFromApi({
  nodeId,
  branchName,
  atDate,
  parseAs = "text",
}: GetObjectFileFromApiParams) {
  return apiClient.GET("/api/storage/files/{node_id}", {
    params: {
      path: {
        node_id: nodeId,
      },
      query: {
        branch: branchName,
        at: atDate?.toISOString() ?? null,
        preview: true,
      },
    },
    parseAs,
  });
}
