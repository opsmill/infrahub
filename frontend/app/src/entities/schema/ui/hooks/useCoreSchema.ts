import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

/**
 * Hook for Core namespace schemas that are guaranteed to exist.
 * Use this for built-in Core* objects like CoreProposedChange, CoreBranch, etc.
 *
 * @param kind - The Core schema kind (e.g., "CoreProposedChange")
 * @returns The schema (non-nullable) - throws if schema not found
 */
export function useCoreSchema(kind: string): ModelSchema {
  const { schema } = useSchema(kind);

  if (!schema) {
    throw new Error(
      `Core schema "${kind}" not found. This should never happen as Core schemas are always loaded.`
    );
  }

  return schema;
}
