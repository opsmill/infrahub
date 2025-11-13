import { apiClient } from "@/shared/api/rest/client";
import type { BranchContextParams } from "@/shared/api/types";

export interface GenerateArtifactFromApiParams extends BranchContextParams {
  artifactDefinitionId: string;
  nodeIds?: Array<string>;
}

export function generateArtifactFromApi({
  artifactDefinitionId,
  nodeIds,
  branchName,
}: GenerateArtifactFromApiParams) {
  return apiClient.POST("/api/artifact/generate/{artifact_definition_id}", {
    params: {
      path: {
        artifact_definition_id: artifactDefinitionId,
      },
      query: {
        branch: branchName,
      },
    },
    body: nodeIds ? { nodes: nodeIds } : undefined,
  });
}
