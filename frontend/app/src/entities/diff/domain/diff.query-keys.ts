import { GetDiffTreeParams } from "@/entities/diff/domain/get-diff-tree";

export const treeQueryKeys = {
  all: ["diff-tree"] as const,
  allWithContext: ({ branchName, filters }: GetDiffTreeParams) =>
    [...treeQueryKeys.all, branchName, filters] as const,
};

export const updateDiffMutationKeys = {
  all: ["update-diff"] as const,
};

export const runCheckMutationKeys = {
  all: ["run-check"] as const,
};

export const proposedChangeValidatorsKeys = {
  all: ["proposed-change-validators"],
  allWithinProposedChange: (proposedChangeId: string) => [
    ...proposedChangeValidatorsKeys.all,
    proposedChangeId,
  ],
};
