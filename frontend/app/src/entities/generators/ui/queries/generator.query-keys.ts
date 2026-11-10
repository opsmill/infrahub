import type { ContextParams } from "@/shared/api/types";

import type { GetNodeGeneratorDefinitionsParams } from "@/entities/generators/domain/use-cases/get-node-generator-definitions";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

export const generatorsQueryKeys = {
  all: (context: ContextParams) =>
    [...objectQueryKeys.allWithContext(context), "generators"] as const,
  nodeDefinitions: ({ branchName, atDate, nodeKind, nodeId }: GetNodeGeneratorDefinitionsParams) =>
    [
      ...generatorsQueryKeys.all({ branchName, atDate }),
      "node-definitions",
      nodeKind,
      nodeId,
    ] as const,
} as const;
