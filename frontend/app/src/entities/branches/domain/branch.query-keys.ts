export const branchesQueryKeys = {
  all: ["branches"],
  details: ({ branchName }: { branchName: string }) => [...branchesQueryKeys.all, branchName],
} as const;
