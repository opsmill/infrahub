import { GLOBAL_PERMISSION_OBJECT, OBJECT_PERMISSION_OBJECT } from "@/shared/config/constants";

import { globalDecisionOptions, objectDecisionOptions } from "@/entities/role-manager/constants";

export type DecisionOption = { value: number; label: string };

export function getDecisionOptions(
  schemaKind: string | null | undefined,
  attributeName: string
): DecisionOption[] | null {
  if (attributeName !== "decision") return null;
  if (schemaKind === OBJECT_PERMISSION_OBJECT) return objectDecisionOptions;
  if (schemaKind === GLOBAL_PERMISSION_OBJECT) return globalDecisionOptions;
  return null;
}
