import { useMutation } from "@tanstack/react-query";
import {
  UpdateProposedChangeCheckStateParams,
  updateProposedChangeCheckState,
} from "./update-proposed-change-check-state";

interface UpdateReviewProps {
  onSuccess?: () => void;
  onError?: () => void;
  onSettled?: () => void;
}

export function useUpdateProposedChangeStateCheck({
  onSuccess,
  onError,
  onSettled,
}: UpdateReviewProps) {
  return useMutation({
    mutationFn: async (params: UpdateProposedChangeCheckStateParams) => {
      return updateProposedChangeCheckState(params);
    },
    onSuccess,
    onError,
    onSettled,
  });
}
