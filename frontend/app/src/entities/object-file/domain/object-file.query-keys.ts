import type { ContextParams } from "@/shared/api/types";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import type { GetObjectFileParams } from "@/entities/object-file/domain/get-object-file";

export const objectFileQueryKeys = {
  all: (context: ContextParams) =>
    [...objectQueryKeys.allWithContext(context), "object-file"] as const,
  file: ({ branchName, atDate, nodeId, contentType }: GetObjectFileParams) =>
    [...objectFileQueryKeys.all({ branchName, atDate }), "file", nodeId, contentType] as const,
} as const;
