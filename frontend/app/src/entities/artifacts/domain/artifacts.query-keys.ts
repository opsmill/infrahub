export const artifactsQueryKeys = {
  all: ["artifacts"] as const,
  file: (storageId: string) => [...artifactsQueryKeys.all, "file", storageId] as const,
} as const;
