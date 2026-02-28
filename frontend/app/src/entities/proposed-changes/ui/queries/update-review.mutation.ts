import { useMutation } from "@tanstack/react-query";

import {
  type UpdateProposedChangeReviewParams,
  updateProposedChangeReview,
} from "@/entities/proposed-changes/domain/update-proposed-change-review";

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
