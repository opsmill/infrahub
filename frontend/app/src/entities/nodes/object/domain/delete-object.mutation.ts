import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { currentBranchAtom } from "@/entities/branches/stores";
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
  const currentBranch = useAtomValue(currentBranchAtom);
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useMutation({
    mutationFn: async ({ objectKind, objectId }: DeleteObjectParams) => {
      await deleteObject({
        objectKind,
        objectId,
        branchName: currentBranch?.name ?? DEFAULT_BRANCH_NAME,
        atDate: timeMachineDate,
      });

      return { objectKind, objectId };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["objects"] });
    },
  });
}
