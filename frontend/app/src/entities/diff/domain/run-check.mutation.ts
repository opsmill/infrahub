import { useMutation } from "@tanstack/react-query";

import { runCheck } from "@/entities/diff/domain/run-check";

export function useRunCheckMutation() {
  return useMutation({
    mutationFn: runCheck,
  });
}
