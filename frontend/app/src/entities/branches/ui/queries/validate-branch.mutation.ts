import { useMutation } from "@tanstack/react-query";

import { validateBranch } from "@/entities/branches/domain/validate-branch";

export function useValidateBranch() {
  return useMutation({
    mutationFn: validateBranch,
  });
}
