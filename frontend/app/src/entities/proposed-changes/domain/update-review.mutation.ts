import {
  UpdateProposedChangeReviewParams,
  updateProposedChangeReview,
} from "@/entities/proposed-changes/domain/update-proposed-change-review";
import { useMutation } from "@tanstack/react-query";

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
    mutationFn: async (params: UpdateProposedChangeReviewParams) => {
      return updateProposedChangeReview(params);
    },
    onSuccess,
    onError,
    onSettled,
  });
}
