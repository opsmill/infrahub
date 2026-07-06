import type { GetSchemaHashParams } from "@/entities/schema/domain/use-cases/get-schema-hash";
import type { LoadSchemaParams } from "@/entities/schema/domain/use-cases/load-schema";

export interface LoadSchemaQueryKeyParams extends LoadSchemaParams {
  schemaHash: string | undefined;
}

export const schemaQueryKeys = {
  all: ["schema"] as const,
  hash: (params: GetSchemaHashParams) => [...schemaQueryKeys.all, "hash", params] as const,
  load: (params: LoadSchemaQueryKeyParams) => [...schemaQueryKeys.all, "load", params] as const,
} as const;
