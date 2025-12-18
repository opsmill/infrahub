import { useMutation } from "@tanstack/react-query";

import { queryClient } from "@/shared/api/rest/client";
import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_STATUS_OPEN } from "@/entities/branches/constants";
import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { branchesQueryKeys } from "@/entities/branches/domain/branch.query-keys";
import { createBranch } from "@/entities/branches/domain/create-branch";
import { getBranchesInfiniteQueryOptions } from "@/entities/branches/domain/get-branches.query";

export function useCreateBranchMutation() {
  const { user } = useAuth();

  return useMutation({
    mutationFn: createBranch,
    onSuccess: async (branchCreated) => {
      if (!branchCreated) return;

      const now = new Date().toISOString();

      // Map mutation response to BranchListItem for cache update
      const branchListItem: BranchListItem = {
        id: branchCreated.id,
        name: branchCreated.name,
        description: branchCreated.description,
        branched_from: branchCreated.branched_from,
        status: BRANCH_STATUS_OPEN,
        sync_with_git: branchCreated.sync_with_git,
        is_default: branchCreated.is_default,
        has_schema_changes: false,
        created_at: branchCreated.created_at ?? now,
        updated_at: now,
        created_by: user?.id
          ? { id: user.id, display_label: null, hfid: null, __typename: ACCOUNT_GENERIC_OBJECT }
          : null,
      };

      const { queryKey } = getBranchesInfiniteQueryOptions();
      queryClient.setQueryData(queryKey, (oldData) => {
        if (!oldData) return oldData;

        return {
          ...oldData,
          pages: oldData.pages.map((page, index) =>
            index === 0 ? [branchListItem, ...page] : page
          ),
        };
      });

      await queryClient.refetchQueries({ queryKey: branchesQueryKeys.all });
    },
  });
}
