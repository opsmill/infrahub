export const artifactsQueryKeys = {
  all: ["artifacts"] as const,
  encryption: (artifactId: string, branchName: string) =>
    [...artifactsQueryKeys.all, "encryption", artifactId, branchName] as const,
  file: (storageId: string, contentType?: string) =>
    [...artifactsQueryKeys.all, "file", storageId, contentType] as const,
} as const;
