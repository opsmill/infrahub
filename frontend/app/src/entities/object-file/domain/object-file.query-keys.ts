export const objectFileQueryKeys = {
  all: ["object-file"] as const,
  file: (nodeId: string, contentType?: string) =>
    [...objectFileQueryKeys.all, "file", nodeId, contentType] as const,
} as const;
