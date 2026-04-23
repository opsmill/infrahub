import { useAtomValue } from "jotai";
import { useMemo } from "react";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

// Namespaces Infrahub ships with. Schemas in any other namespace are user-defined.
const BUILTIN_NAMESPACES = new Set(["Builtin", "Core", "Infrahub", "Internal", "Profile", "Template"]);

/**
 * Returns true when the active branch has at least one user-defined schema node loaded.
 *
 * Drives the Schema Marketplace home tile's onboarding call-to-action (FR-004):
 * when this returns false, the tile surfaces "Get started — install your first
 * schema"; when true, the tile shows its default label.
 */
export function useHasUserSchemas(): boolean {
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  return useMemo(() => {
    for (const node of nodeSchemas) {
      if (!BUILTIN_NAMESPACES.has(node.namespace)) {
        return true;
      }
    }
    return false;
  }, [nodeSchemas]);
}
