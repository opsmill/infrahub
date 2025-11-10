export const branchesQueryKeys = {
  all: ["branches"] as const,
  details: ({ branchName }: { branchName: string }) => [...branchesQueryKeys.all, branchName],
} as const;
