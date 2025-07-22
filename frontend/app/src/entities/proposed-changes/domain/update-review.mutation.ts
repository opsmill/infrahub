import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useMutation } from "@tanstack/react-query";
import { UpdateReviewFromApiApiParams } from "../api/updateReviewFromApi";
import { updateReview } from "./update-review";

interface UpdateReviewProps {
  onSuccess?: () => void;
  onError?: () => void;
  onSettled?: () => void;
}

export function useUpdateReview({ onSuccess, onError, onSettled }: UpdateReviewProps) {
  const { currentBranch } = useCurrentBranch();

  return useMutation({
    mutationFn: async (params: Omit<UpdateReviewFromApiApiParams, "branchName">) => {
      return updateReview({
        ...params,
        branchName: currentBranch.name,
      });
    },
    mutationKey: ["propose-changes-action"],
    onSuccess,
    onError,
    onSettled,
  });
}
