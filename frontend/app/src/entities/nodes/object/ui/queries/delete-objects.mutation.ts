import type { DefaultContext } from "@apollo/client";
import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { DeleteObjectsParams } from "@/entities/nodes/object/api/delete-objects-from-api";
import { deleteObjects } from "@/entities/nodes/object/domain/delete-objects";

interface DeleteObjectsProps {
  context?: DefaultContext;
  onSuccess?: () => void;
  onError?: () => void;
  onSettled?: () => void;
}

export function useDeleteObjects({ context, onSuccess, onError, onSettled }: DeleteObjectsProps) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useMutation({
    mutationFn: async ({ objects }: DeleteObjectsParams) => {
      await deleteObjects({
        objects,
        branchName: currentBranch.name,
        atDate: timeMachineDate,
        context,
      });

      return { objects };
    },
    onSuccess,
    onError,
    onSettled,
  });
}
