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

type DiffCommentsKeyParams = {
  proposedChangeId: string;
  objectPath: string;
};

export const diffCommentsKeys = {
  all: ["diff-comments"] as const,
  detail: (params: DiffCommentsKeyParams) => [...diffCommentsKeys.all, "detail", params] as const,
};

type DiffThreadKeyParams = {
  proposedChangeId: string;
  objectPath: string;
};

export const diffThreadKeys = {
  all: ["diff-thread"] as const,
  detail: (params: DiffThreadKeyParams) => [...diffThreadKeys.all, "detail", params] as const,
};

type ArtifactContentDiffKeyParams = {
  proposedChangeId: string;
};

export const artifactContentDiffKeys = {
  all: ["artifact-content-diff"] as const,
  detail: (params: ArtifactContentDiffKeyParams) =>
    [...artifactContentDiffKeys.all, "detail", params] as const,
};

type FileContentDiffKeyParams = {
  proposedChangeId: string;
};

export const fileContentDiffKeys = {
  all: ["file-content-diff"] as const,
  detail: (params: FileContentDiffKeyParams) =>
    [...fileContentDiffKeys.all, "detail", params] as const,
};

type ValidatorDetailsKeyParams = {
  validatorId: string;
  checksOffset?: number;
  checksLimit?: number;
};

export const validatorDetailsKeys = {
  all: ["validator-details"] as const,
  detail: (params: ValidatorDetailsKeyParams) =>
    [...validatorDetailsKeys.all, "detail", params] as const,
};
