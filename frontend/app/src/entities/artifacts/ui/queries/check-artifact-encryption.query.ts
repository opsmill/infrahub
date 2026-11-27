import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { checkArtifactEncryption } from "@/entities/artifacts/domain/use-cases/check-artifact-encryption";
import { artifactsQueryKeys } from "@/entities/artifacts/ui/queries/artifacts.query-keys";
import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export function useCheckArtifactEncryption(artifactId: string) {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);
  const { isAuthenticated } = useAuth();

  return useQuery({
    queryKey: artifactsQueryKeys.encryption(artifactId, currentBranch.name),
    queryFn: async () => {
      const result = await checkArtifactEncryption({
        artifactId,
        branchName: currentBranch.name,
      });
      // The backend stores a changed result on the artifact.
      if (result.updated) {
        await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      }
      return result;
    },
    // The check needs a signed-in user and reads the file as it is now.
    enabled: isAuthenticated && timeMachineDate === null,
    staleTime: 0,
    refetchOnWindowFocus: false,
  });
}
