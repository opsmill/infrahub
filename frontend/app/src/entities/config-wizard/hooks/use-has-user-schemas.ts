import { useAtomValue } from "jotai";

import {
  genericSchemasAtom,
  namespacesAtom,
  nodeSchemasAtom,
} from "@/entities/schema/stores/schema.atom";

/**
 * Namespaces that ship with a fresh Infrahub instance.
 * These are excluded when checking for user-defined schemas.
 */
const DEFAULT_NAMESPACES = new Set([
  "Account",
  "Branch",
  "Builtin",
  "Core",
  "Deprecated",
  "Diff",
  "Infrahub",
  "Internal",
  "Ipam",
  "Lineage",
  "Profile",
  "Schema",
  "Template",
]);

/**
 * Returns true if user-defined schemas exist (schemas in namespaces not shipped with core).
 * Used to determine whether to show the configuration wizard.
 */
export function useHasUserSchemas(): boolean {
  const namespaces = useAtomValue(namespacesAtom);
  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const genericSchemas = useAtomValue(genericSchemasAtom);

  const userNamespaces = namespaces
    .filter((ns) => ns.user_editable && !DEFAULT_NAMESPACES.has(ns.name))
    .map((ns) => ns.name);

  if (userNamespaces.length === 0) {
    return false;
  }

  const allSchemas = [...nodeSchemas, ...genericSchemas];
  return allSchemas.some((schema) => userNamespaces.includes(schema.namespace ?? ""));
}
