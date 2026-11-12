import { apiClient } from "@/shared/api/rest/client";
import type { BranchContextParams } from "@/shared/api/types";

export interface CheckArtifactEncryptionFromApiParams extends BranchContextParams {
  artifactId: string;
}

export function checkArtifactEncryptionFromApi({
  artifactId,
  branchName,
}: CheckArtifactEncryptionFromApiParams) {
  return apiClient.POST("/api/artifact/{artifact_id}/encryption", {
    params: {
      path: { artifact_id: artifactId },
      query: { branch: branchName },
    },
  });
}
