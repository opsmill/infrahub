import { isDeepEqual } from "remeda";

import type {
  AttributeValueFromPool,
  FormAttributeValue,
  FormFieldValue,
  FormRelationshipValue,
  PoolValue,
  RelationshipValueFromPool,
} from "@/shared/components/form/type";
import { makePoolSource } from "@/shared/components/form/utils/make-pool-source";

/**
 * The concrete kind a pool field's value points at: a resolved node's `__typename`, or the
 * requested `allocatedKind` while the allocation is still pending.
 */
export const getAllocatedKind = (value: FormFieldValue["value"]): string | undefined => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return undefined;
  return "from_pool" in value ? value.from_pool.allocatedKind : value.__typename;
};

/** Whether re-selecting the field's original pool would leave the allocated kind alone. */
const keepsAllocatedKind = (requestedKind: string | undefined, current: FormFieldValue["value"]) =>
  !requestedKind || requestedKind === getAllocatedKind(current);

export const updateFormFieldValue = (
  newValue: Exclude<FormFieldValue, AttributeValueFromPool | RelationshipValueFromPool>["value"],
  defaultValue?: FormFieldValue
): FormFieldValue => {
  if (defaultValue && isDeepEqual(newValue, defaultValue.value as typeof newValue)) {
    return defaultValue;
  }

  return {
    source: { type: "user" },
    value: newValue,
  };
};

export const updateAttributeFieldValue = (
  newValue: { id: string } | { id: string }[] | PoolValue | null,
  defaultValue?: FormAttributeValue
): FormAttributeValue => {
  if (newValue && "from_pool" in newValue) {
    if (
      defaultValue?.source?.type === "pool" &&
      defaultValue.source.id === newValue.from_pool.id &&
      keepsAllocatedKind(newValue.from_pool.allocatedKind, defaultValue.value)
    ) {
      // Re-selecting the field's original pool restores the existing allocation
      // unchanged. Allocation is idempotent on the reservation identifier, so the
      // original pool cannot be re-allocated with a different mask — show the
      // resolved value rather than a pending allocation with an editable length.
      // No reservation identifier is sent for the kind, so a different kind is a fresh allocation
      // and must fall through.
      return defaultValue;
    }
    return {
      source: makePoolSource({
        id: newValue.from_pool.id,
        kind: newValue.from_pool.kind,
        label: newValue.from_pool.name,
        defaultPrefixLength: newValue.from_pool.defaultPrefixLength ?? null,
        defaultAllocatedKind: newValue.from_pool.defaultAllocatedKind ?? null,
      }),
      value: {
        from_pool: {
          id: newValue.from_pool.id,
          ...(newValue.from_pool.prefixLength !== undefined && {
            prefixLength: newValue.from_pool.prefixLength,
          }),
          // Kept in the value rather than the source because it is sent to the API.
          ...(newValue.from_pool.allocatedKind !== undefined && {
            allocatedKind: newValue.from_pool.allocatedKind,
          }),
        },
      },
    };
  }

  return updateFormFieldValue(newValue, defaultValue) as FormAttributeValue;
};

export const updateRelationshipFieldValue = (
  newValue: { id: string } | { id: string }[] | PoolValue | null,
  defaultValue?: FormRelationshipValue
): FormRelationshipValue => {
  if (newValue && "from_pool" in newValue) {
    if (
      defaultValue?.source?.type === "pool" &&
      defaultValue.source.id === newValue.from_pool.id &&
      keepsAllocatedKind(newValue.from_pool.allocatedKind, defaultValue.value)
    ) {
      // Re-selecting the field's original pool restores the existing allocation
      // unchanged. Allocation is idempotent on the reservation identifier, so the
      // original pool cannot be re-allocated with a different mask — show the
      // resolved value rather than a pending allocation with an editable length.
      // No reservation identifier is sent for the kind, so a different kind is a fresh allocation
      // and must fall through.
      return defaultValue;
    }
    return {
      source: makePoolSource({
        id: newValue.from_pool.id,
        kind: newValue.from_pool.kind,
        label: newValue.from_pool.name,
        defaultPrefixLength: newValue.from_pool.defaultPrefixLength ?? null,
        defaultAllocatedKind: newValue.from_pool.defaultAllocatedKind ?? null,
      }),
      value: {
        from_pool: {
          id: newValue.from_pool.id,
          ...(newValue.from_pool.prefixLength !== undefined && {
            prefixLength: newValue.from_pool.prefixLength,
          }),
          // Kept in the value rather than the source because it is sent to the API.
          ...(newValue.from_pool.allocatedKind !== undefined && {
            allocatedKind: newValue.from_pool.allocatedKind,
          }),
        },
      },
    };
  }

  return updateFormFieldValue(newValue, defaultValue) as FormRelationshipValue;
};
