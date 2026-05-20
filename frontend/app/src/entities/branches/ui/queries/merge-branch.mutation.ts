import { useMutation } from "@tanstack/react-query";

import { mergeBranch } from "@/entities/branches/domain/merge-branch";

export function useMergeBranch() {
  return useMutation({
    mutationFn: mergeBranch,
  });
}
