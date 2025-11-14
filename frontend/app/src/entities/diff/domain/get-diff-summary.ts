import {
  type GetDiffTreeSummaryFromApiParams,
  getDiffTreeSummaryFromApi,
} from "@/entities/diff/api/get-diff-tree-summary-from-api";

export type GetDiffSummaryParams = GetDiffTreeSummaryFromApiParams;

export type GetDiffSummaryResponse = {
  num_added: number;
  num_updated: number;
  num_removed: number;
  num_conflicts: number;
};

export type GetDiffSummary = (
  params: GetDiffSummaryParams
) => Promise<GetDiffSummaryResponse | null>;

export const getDiffSummary: GetDiffSummary = async (params) => {
  const { data, errors } = await getDiffTreeSummaryFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return (data.DiffTreeSummary as GetDiffSummaryResponse) ?? null;
};
