export const repositoryQueryKeys = {
  all: ["repository"] as const,
  syncHealth: (branch: string) => [...repositoryQueryKeys.all, "sync-health", branch] as const,
};
