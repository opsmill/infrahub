import { useMutation } from "@tanstack/react-query";

import type { Branch } from "@/shared/api/graphql/generated/graphql";

import { rebaseBranchFromApi } from "@/entities/branches/api/rebase-branch-from-api";

export type RebaseBranchParams = {
  branchName: string;
  waitUntilCompletion?: boolean;
};

export type RebaseBranch = (params: RebaseBranchParams) => Promise<{
  branch: Branch;
  relatedTaskId: string | null;
}>;

export const rebaseBranch: RebaseBranch = async ({
  branchName,
  waitUntilCompletion = true,
}: RebaseBranchParams) => {
  const { data } = await rebaseBranchFromApi({ branchName, waitUntilCompletion });

  return {
    branch: data.BranchRebase.object,
    relatedTaskId: data.BranchRebase.task?.id ?? null,
  };
};

export const useRebaseBranch = () => {
  return useMutation({
    mutationFn: rebaseBranch,
  });
};
