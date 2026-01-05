import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import {
  type AddRelationshipsParams,
  addRelationships,
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
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
