import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import {
  type RemoveRelationshipsParams,
  removeRelationships,
} from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships";

export function useRemoveRelationships() {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: async ({
      objectId,
      relationshipName,
      relationshipIds,
    }: Omit<RemoveRelationshipsParams, "branchName">) => {
      await removeRelationships({
        objectId,
        relationshipName,
        relationshipIds,
        branchName: currentBranch.name,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
