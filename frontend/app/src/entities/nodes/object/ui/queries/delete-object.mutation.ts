import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { queryClient } from "@/shared/api/rest/client";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { deleteObject } from "@/entities/nodes/object/domain/delete-object";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export interface DeleteObjectParams {
  objectKind: string;
  objectId: string;
}

export function useDeleteObjectMutation() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useMutation({
    mutationFn: async ({ objectKind, objectId }: DeleteObjectParams) => {
      await deleteObject({
        objectKind,
        objectId,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      });

      return { objectKind, objectId };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });
}
