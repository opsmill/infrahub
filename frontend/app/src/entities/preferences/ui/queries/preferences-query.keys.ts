export const preferencesQueryKeys = {
  all: ["preferences"] as const,
  effective: () => [...preferencesQueryKeys.all, "effective"] as const,
} as const;
