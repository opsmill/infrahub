import { REPOSITORY_PUSH_STATE_ATTRIBUTE_NAMES } from "@/entities/repository/domain/model/repository";

/** Another branch holds an old copy of these, and the push to remote card shows the live value, so the repository's attribute lists and columns leave them out. */
export function isPushStateAttribute(fieldName: string): boolean {
  return REPOSITORY_PUSH_STATE_ATTRIBUTE_NAMES.includes(fieldName);
}
