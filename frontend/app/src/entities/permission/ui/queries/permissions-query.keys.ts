export const globalPermissionQueryKeys = {
  all: () => ["permissions", "global"] as const,
  byAction: (userId: string | undefined, action: string) =>
    [...globalPermissionQueryKeys.all(), userId, action] as const,
} as const;
