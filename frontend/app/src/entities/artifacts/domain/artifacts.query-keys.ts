export const artifactsQueryKeys = {
  all: ["artifacts"] as const,
  file: (storageId: string, contentType?: string) =>
    [...artifactsQueryKeys.all, "file", storageId, contentType] as const,
} as const;
