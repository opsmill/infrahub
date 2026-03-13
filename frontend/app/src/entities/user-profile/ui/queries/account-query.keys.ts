export const accountQueryKeys = {
  all: ["account-profile"] as const,
  details: () => [...accountQueryKeys.all, "details"] as const,
  tokens: () => [...accountQueryKeys.all, "tokens"] as const,
} as const;
