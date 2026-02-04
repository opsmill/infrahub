export const objectFileQueryKeys = {
  all: ["object-file"] as const,
  file: (nodeId: string) => [...objectFileQueryKeys.all, "file", nodeId] as const,
} as const;
