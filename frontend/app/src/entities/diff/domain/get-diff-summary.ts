import { getDiffTreeSummaryFromApi } from "@/entities/diff/api/get-diff-tree-summary-from-api";

export type GetDiffSummaryParams = { branchName: string };

export type GetDiffSummaryResponse = {
  num_added: number;
  num_updated: number;
  num_removed: number;
  num_conflicts: number;
};

export type GetDiffSummary = (
  params: GetDiffSummaryParams
) => Promise<GetDiffSummaryResponse | null>;

export const getDiffSummary: GetDiffSummary = async ({ branchName }) => {
  const { data, errors } = await getDiffTreeSummaryFromApi({
    branch: branchName,
  });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return (data.DiffTreeSummary as GetDiffSummaryResponse) ?? null;
};
