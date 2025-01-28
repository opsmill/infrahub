import { getCurrentBranchName } from "@/entities/branches/domain/get-current-branch";
import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useMutation } from "@tanstack/react-query";
import { deleteObject } from "./delete-object";

export interface DeleteObjectParams {
  objectKind: string;
  objectId: string;
}

export function useDeleteObject() {
  const currentBranchName = getCurrentBranchName();
  const timeMachineDate = store.get(datetimeAtom);

  return useMutation({
    mutationFn: async ({ objectKind, objectId }: DeleteObjectParams) => {
      await deleteObject({
        objectKind,
        objectId,
        branchName: currentBranchName,
        atDate: timeMachineDate,
      });

      return { objectKind, objectId };
    },
    onSuccess: ({ objectKind }) => {
      queryClient.invalidateQueries({ queryKey: ["objects", objectKind] });
    },
  });
}
