import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { queryClient } from "@/shared/api/rest/client";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { deleteObjects } from "./delete-objects";

export interface DeleteObjectsParams {
  objectKind: string;
  objectIds: Array<string>;
}

export function useDeleteObjects() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useMutation({
    mutationFn: async ({ objectKind, objectIds }: DeleteObjectsParams) => {
      await deleteObjects({
        objectKind,
        objectIds,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      });

      return { objectKind, objectIds };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes("objects"),
      });
    },
  });
}
