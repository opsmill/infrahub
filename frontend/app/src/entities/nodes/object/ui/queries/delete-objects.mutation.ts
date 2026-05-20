import { useMutation } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type {
  DeleteObjectsFromApiParams,
  ObjectParam,
} from "@/entities/nodes/object/api/delete-objects-from-api";
import { deleteObjects } from "@/entities/nodes/object/domain/delete-objects";

export interface DeleteObjectsContext {
  processErrorMessage?: (message: string) => void;
}

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
    onSuccess,
    onError,
    onSettled,
  });
}
