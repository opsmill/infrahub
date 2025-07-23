import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useMutation } from "@tanstack/react-query";
import { UpdateReviewFromApiApiParams } from "../api/updateProposedChangeReviewFromApi";
import { updateProposedChangeReview } from "./update-review";

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
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: async (params: Omit<UpdateReviewFromApiApiParams, "branchName">) => {
      return updateProposedChangeReview({
        ...params,
        branchName: currentBranch.name,
      });
    },
    onSuccess,
    onError,
    onSettled,
  });
}
