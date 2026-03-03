import { useMutation } from "@tanstack/react-query";

import { rebaseBranch } from "@/entities/branches/domain/rebase-branch";

export const useRebaseBranch = () => {
  return useMutation({
    mutationFn: rebaseBranch,
  });
};
