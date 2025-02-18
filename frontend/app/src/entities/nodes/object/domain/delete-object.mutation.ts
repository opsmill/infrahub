import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { queryClient } from "@/shared/api/rest/client";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { deleteObject } from "./delete-object";

export interface DeleteObjectParams {
  objectKind: string;
  objectId: string;
}

export function useDeleteObject() {
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
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes("objects"),
      });
    },
  });
}
