import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  RemoveRelationshipsParams,
  removeRelationships,
} from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships";
import { queryClient } from "@/shared/api/rest/client";
import { useMutation } from "@tanstack/react-query";

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
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes("objects"),
      });
    },
  });
}
