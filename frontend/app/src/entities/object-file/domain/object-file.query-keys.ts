export const objectFileQueryKeys = {
  all: ["object-file"] as const,
  file: (nodeId: string, branchName: string, atDate?: Date | null, contentType?: string) =>
    [...objectFileQueryKeys.all, "file", nodeId, branchName, atDate, contentType] as const,
} as const;
