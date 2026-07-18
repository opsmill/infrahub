import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";

import {
  type CreateProposedChangeParams,
  createProposedChange,
} from "@/entities/proposed-changes/domain/create-proposed-change";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/ui/queries/proposed-changes.query-keys";

export function useCreateProposedChange() {
  return useMutation({
    mutationFn: (params: CreateProposedChangeParams) => createProposedChange(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: proposedChangesQueryKeys.all });
    },
  });
}
