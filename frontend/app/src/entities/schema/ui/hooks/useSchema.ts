import { useAtomValue } from "jotai";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { resolveSchema, type SchemaResult } from "@/entities/schema/utils/resolve-schema";

/**
 * Hook for retrieving schemas with optional required behavior.
 *
 * @param kind - The schema kind to retrieve
 * @param options - Configuration options
 * @param options.required - If true, throws error when schema not found.
 * @returns Schema result with type flags. Schema is non-nullable when required: true.
 *
 * @example
 * // Optional schema (nullable)
 * const { schema } = useSchema(dynamicKind);
 * if (!schema) return <NotFound />;
 *
 * @example
 * // Required schema (non-nullable, throws if missing)
 * const { schema } = useSchema("CoreProposedChange", { required: true });
 */

export function useSchema(
  kind: string | null | undefined,
  options: { throwIfNotFound: true }
): Exclude<SchemaResult, { schema: null }>;

export function useSchema(
  kind: string | null | undefined,
  options?: { throwIfNotFound?: false }
): SchemaResult;

export function useSchema(
  kind: string | null | undefined,
  options?: { throwIfNotFound?: boolean }
) {
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const profileSchemas = useAtomValue(profileSchemasAtom);
  const genericSchemas = useAtomValue(genericSchemasAtom);
  const templateSchemas = useAtomValue(templateSchemasAtom);

  const result = resolveSchema(kind, {
    nodeSchemas,
    genericSchemas,
    profileSchemas,
    templateSchemas,
  });

  if (options?.throwIfNotFound && !result.schema) {
    throw new Error(
      `Required schema "${kind}" not found. This indicates the schema is not loaded or does not exist.`
    );
  }

  return result;
}
