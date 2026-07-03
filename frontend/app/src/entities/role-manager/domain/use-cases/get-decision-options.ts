import {
  GLOBAL_PERMISSION_OBJECT,
  OBJECT_PERMISSION_OBJECT,
} from "@/entities/permission/domain/model/permission";
import {
  globalDecisionOptions,
  objectDecisionOptions,
} from "@/entities/role-manager/domain/model/decision";

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
