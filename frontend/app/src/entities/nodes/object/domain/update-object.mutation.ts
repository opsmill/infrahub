import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { UpdateObjectParams, updateObject } from "@/entities/nodes/object/domain/update-object";
import { useMutation } from "@tanstack/react-query";

interface UpdateObjectProps {
  onSuccess?: () => void;
  onError?: () => void;
  onSettled?: () => void;
}

export function useUpdateObjectMutation({ onSuccess, onError, onSettled }: UpdateObjectProps) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: (params: Omit<UpdateObjectParams, "branchName">) => {
      return updateObject({
        branchName: currentBranch.name,
        ...params,
      });
    },
    onSuccess,
    onError,
    onSettled,
  });
}
