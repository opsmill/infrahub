import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

type CoreSchemaResult =
  | {
      schema: ModelSchema;
      isGeneric: true;
      isNode: false;
      isProfile: false;
      isTemplate: false;
    }
  | {
      schema: ModelSchema;
      isGeneric: false;
      isNode: true;
      isProfile: false;
      isTemplate: false;
    }
  | {
      schema: ModelSchema;
      isGeneric: false;
      isNode: false;
      isProfile: true;
      isTemplate: false;
    }
  | {
      schema: ModelSchema;
      isGeneric: false;
      isNode: false;
      isProfile: false;
      isTemplate: true;
    };

/**
 * Hook for Core namespace schemas that are guaranteed to exist.
 * Use this for built-in Core* objects like CoreProposedChange, CoreBranch, etc.
 *
 * @param kind - The Core schema kind (e.g., "CoreProposedChange")
 * @returns The schema result with type flags (non-nullable) - throws if schema not found
 */
export function useCoreSchema(kind: string): CoreSchemaResult {
  const schemaResult = useSchema(kind);

  if (!schemaResult.schema) {
    throw new Error(
      `Core schema "${kind}" not found. This should never happen as Core schemas are always loaded.`
    );
  }

  return schemaResult as CoreSchemaResult;
}
