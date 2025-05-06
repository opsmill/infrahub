import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { DeleteObjectsParams } from "@/entities/nodes/object/api/delete-objects-from-api";
import { queryClient } from "@/shared/api/rest/client";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { deleteObjects } from "./delete-objects";

export function useDeleteObjects() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useMutation({
    mutationFn: async ({ objects }: DeleteObjectsParams) => {
      await deleteObjects({
        objects,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
      });

      return { objects };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes("objects"),
      });
    },
  });
}
