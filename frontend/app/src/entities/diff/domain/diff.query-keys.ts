type TreeQueryKeyParams = {
  branchName: string;
  filters?: unknown;
  proposedChangeId?: string;
};

export const treeQueryKeys = {
  all: ["diff-tree"] as const,
  allWithContext: ({ branchName, filters, proposedChangeId }: TreeQueryKeyParams) =>
    [...treeQueryKeys.all, branchName, filters, proposedChangeId] as const,
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

export const artifactsDiffKeys = {
  all: ["artifacts-diff"] as const,
  list: (branch: string) => [...artifactsDiffKeys.all, branch] as const,
};

export const filesDiffKeys = {
  all: ["files-diff"] as const,
  list: (branch: string) => [...filesDiffKeys.all, branch] as const,
};

type FileKeyParams = {
  repositoryId: string;
  filePath: string;
  commit?: string;
};

export const fileKeys = {
  all: ["file"] as const,
  detail: ({ repositoryId, filePath, commit }: FileKeyParams) =>
    [...fileKeys.all, repositoryId, filePath, commit] as const,
};
