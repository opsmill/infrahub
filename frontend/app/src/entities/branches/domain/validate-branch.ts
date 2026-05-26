import {
  type ValidateBranchFromApiParams,
  validateBranchFromApi,
} from "@/entities/branches/api/validate-branch-from-api";

export type ValidateBranchParams = ValidateBranchFromApiParams;

export interface ValidateBranchOutcome {
  ok: boolean;
  taskId: string | null;
}

export async function validateBranch(params: ValidateBranchParams): Promise<ValidateBranchOutcome> {
  const { data, errors } = await validateBranchFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return {
    ok: data?.BranchValidate?.ok ?? false,
    taskId: data?.BranchValidate?.task?.id ?? null,
  };
}
