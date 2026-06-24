import { useMutation } from "@tanstack/react-query";

import type { MutationConfig } from "@/shared/api/types";

import {
  type UpdateProposedChangeReviewParams,
  updateProposedChangeReview,
} from "@/entities/proposed-changes/domain/update-proposed-change-review";

interface UseUpdateProposedChangeReviewParams
  extends MutationConfig<typeof updateProposedChangeReview> {}

export function useUpdateProposedChangeReview(params: UseUpdateProposedChangeReviewParams) {
  return useMutation({
    mutationFn: async (params: UpdateProposedChangeReviewParams) => {
      return updateProposedChangeReview(params);
    },
    ...params,
  });
}
