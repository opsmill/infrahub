export const branchesQueryKeys = {
  all: ["branches"] as const,
  list: (params: { branchSearch?: string }) => [...branchesQueryKeys.all, "list", params] as const,
  count: (branchSearch?: string) => [...branchesQueryKeys.all, "count", branchSearch] as const,
  details: ({ branchName }: { branchName: string }) => [...branchesQueryKeys.all, branchName],
} as const;
