export const branchesQueryKeys = {
  all: ["branches"] as const,
  list: (search?: string) => [...branchesQueryKeys.all, "list", { search }] as const,
  count: (search?: string) => [...branchesQueryKeys.all, "count", { search }] as const,
  details: ({ branchName }: { branchName: string }) => [...branchesQueryKeys.all, branchName],
} as const;
