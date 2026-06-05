import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type {
  DeleteObjectsContext,
  DeleteObjectsFromApiParams,
  ObjectParam,
} from "@/entities/nodes/object/api/delete-objects-from-api";
import { deleteObjects } from "@/entities/nodes/object/domain/delete-objects";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

interface DeleteObjectsProps {
  context?: DeleteObjectsContext;
  onSuccess?: () => void;
  onError?: () => void;
  onSettled?: () => void;
}

export function useDeleteObjects({ context, onSuccess, onError, onSettled }: DeleteObjectsProps) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: async ({ objects }: { objects: ObjectParam[] }) => {
      const domainParams: DeleteObjectsFromApiParams = {
        objects,
        branchName: currentBranch.name,
        context: context ?? {},
      };

      await deleteObjects(domainParams);

      return { objects };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      onSuccess?.();
    },
    onError,
    onSettled,
  });
}
