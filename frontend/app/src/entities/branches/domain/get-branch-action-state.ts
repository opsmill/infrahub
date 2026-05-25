import {
  type GetBranchActionStateFromApiParams,
  getBranchActionStateFromApi,
} from "@/entities/branches/api/get-branch-action-state-from-api";

export type GetBranchActionStateParams = GetBranchActionStateFromApiParams;

export interface BranchActionState {
  ongoingTaskCount: number;
}

export async function getBranchActionState(
  params: GetBranchActionStateParams
): Promise<BranchActionState> {
  const { data, errors } = await getBranchActionStateFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return {
    ongoingTaskCount: data?.InfrahubTask?.count ?? 0,
  };
}
