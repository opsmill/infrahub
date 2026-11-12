import { useQuery, useQueryClient } from "@tanstack/react-query";

import { checkArtifactEncryption } from "@/entities/artifacts/domain/use-cases/check-artifact-encryption";
import { artifactsQueryKeys } from "@/entities/artifacts/ui/queries/artifacts.query-keys";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

/**
 * Checks from the stored file's header whether an artifact is readable with the current key.
 * The backend stores the result on the artifact when it changed, so the artifact is fetched again then.
 */
export const useCheckArtifactEncryption = (artifactId: string) => {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    queryKey: artifactsQueryKeys.encryption(artifactId, currentBranch.name),
    queryFn: async () => {
      const result = await checkArtifactEncryption({
        artifactId,
        branchName: currentBranch.name,
      });
      if (result.updated) {
        await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      }
      return result;
    },
    staleTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });
};
