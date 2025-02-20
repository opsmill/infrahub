import { rebaseBranchFromApi } from "@/entities/branches/api/rebase-branch-from-api";
import { Branch } from "@/shared/api/graphql/generated/graphql";
import { useMutation } from "@tanstack/react-query";

export type RebaseBranchParams = {
  branchName: string;
  waitForCompletion?: boolean;
};

export type RebaseBranch = (params: RebaseBranchParams) => Promise<{
  branch: Branch;
  relatedTaskId: string | null;
}>;

export const rebaseBranch: RebaseBranch = async ({
  branchName,
  waitForCompletion = true,
}: RebaseBranchParams) => {
  const { data } = await rebaseBranchFromApi({ branchName, waitForCompletion });

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
