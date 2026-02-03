export const fileContentQueryKeys = {
  all: ["file-content"] as const,
  byUrl: (url: string) => [...fileContentQueryKeys.all, url] as const,
} as const;
