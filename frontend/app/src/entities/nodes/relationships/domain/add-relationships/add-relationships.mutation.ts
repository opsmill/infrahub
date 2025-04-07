import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useMutation } from "@tanstack/react-query";
import { queryClient } from "@/shared/api/rest/client";
import {
  addRelationships,
  AddRelationshipsParams,
} from "@/entities/nodes/relationships/domain/add-relationships/add-relationships";

export function useAddRelationships() {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: async ({
      objectId,
      relationshipName,
      relationshipIds,
    }: Omit<AddRelationshipsParams, "branchName">) => {
      await addRelationships({
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
