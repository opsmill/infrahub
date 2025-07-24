import { ContextParams } from "@/shared/api/types";
import { useMutation } from "@tanstack/react-query";
import {
  UpdateProposedChangeReviewParams,
  updateProposedChangeReview,
} from "./update-proposed-change-review";

interface UpdateReviewProps {
  onSuccess?: () => void;
  onError?: () => void;
  onSettled?: () => void;
}

export function useUpdateProposedChangeReview({
  onSuccess,
  onError,
  onSettled,
}: UpdateReviewProps) {
  return useMutation({
    mutationFn: async (params: Omit<UpdateProposedChangeReviewParams, keyof ContextParams>) => {
      return updateProposedChangeReview(params);
    },
    onSuccess,
    onError,
    onSettled,
  });
}
