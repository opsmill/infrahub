import { GetDiffTreeParams } from "@/entities/diff/domain/get-diff-tree";

export const treeQueryKeys = {
  all: ["diff-tree"] as const,
  allWithContext: ({ branchName, filters }: GetDiffTreeParams) =>
    [...treeQueryKeys.all, branchName, filters] as const,
};

export const updateDiffMutationKeys = {
  all: ["update-diff"] as const,
};

export const getCheckQueryKeys = {
  all: ["checks"] as const,
  details: (checkId: string) => [...getCheckQueryKeys.all, checkId] as const,
};

export const proposedChangeValidatorsKeys = {
  all: ["proposed-change-validators"] as const,
  allWithinProposedChange: (proposedChangeId: string) =>
    [...proposedChangeValidatorsKeys.all, proposedChangeId] as const,
};
