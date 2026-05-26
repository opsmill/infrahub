import {
  type MergeBranchFromApiParams,
  mergeBranchFromApi,
} from "@/entities/branches/api/merge-branch-from-api";

export type MergeBranchParams = MergeBranchFromApiParams;

export interface MergeBranchOutcome {
  ok: boolean;
  taskId: string | null;
}

export async function mergeBranch(params: MergeBranchParams): Promise<MergeBranchOutcome> {
  const { data, errors } = await mergeBranchFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return {
    ok: data?.BranchMerge?.ok ?? false,
    taskId: data?.BranchMerge?.task?.id ?? null,
  };
}
