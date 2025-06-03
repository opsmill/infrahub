import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { reloadIpamTreeAtom } from "@/entities/ipam/ipam-tree/ipam-tree.state";
import { queryClient } from "@/shared/api/rest/client";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useMutation } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { useLocation, useParams } from "react-router";
import { deleteObject } from "./delete-object";

export interface DeleteObjectParams {
  objectKind: string;
  objectId: string;
}

export function useDeleteObject() {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  ////// IPAM Specific, to be improved
  const location = useLocation();
  const { objectId } = useParams();
  const reloadIpamTree = useSetAtom(reloadIpamTreeAtom);
  //////

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

      ////// IPAM Specific, to be improved
      if (location.pathname.startsWith("/ipam")) {
        reloadIpamTree(objectId);
      }
      //////
    },
  });
}
