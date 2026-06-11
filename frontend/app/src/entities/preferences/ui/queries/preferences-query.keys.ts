export const preferencesQueryKeys = {
  all: ["preferences"] as const,
  effective: () => [...preferencesQueryKeys.all, "effective"] as const,
  global: () => [...preferencesQueryKeys.all, "global"] as const,
  user: (accountId?: string) => [...preferencesQueryKeys.all, "user", accountId] as const,
} as const;
