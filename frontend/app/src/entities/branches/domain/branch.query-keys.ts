export const branchesQueryKeys = {
  all: ["branches"] as const,
  list: (params: { branchName?: string }) => [...branchesQueryKeys.all, "list", params] as const,
  details: ({ branchName }: { branchName: string }) => [...branchesQueryKeys.all, branchName],
} as const;
