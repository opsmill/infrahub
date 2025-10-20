import { useMutation } from "@tanstack/react-query";

import { UpdateCheckFromApiParams } from "@/entities/diff/api/run-check-from-api";
import { runCheckMutationKeys } from "@/entities/diff/domain/diff.query-keys";
import { runCheck } from "@/entities/diff/domain/run-check";

export function useRunCheckMutation() {
  return useMutation({
    mutationKey: runCheckMutationKeys.all,
    mutationFn: (params: UpdateCheckFromApiParams) => runCheck(params),
  });
}
