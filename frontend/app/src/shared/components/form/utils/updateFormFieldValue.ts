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
 * The concrete node kind a pool field's current value points at. A resolved relationship
 * holds the allocated node, so its kind is that node's `__typename`; a value still
 * awaiting allocation holds the requested `allocatedKind` instead. Anything else (a plain
 * attribute value, a list, an empty field) points at no kind.
 */
export const getAllocatedKind = (value: FormFieldValue["value"]): string | undefined => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return undefined;
  return "from_pool" in value ? value.from_pool.allocatedKind : value.__typename;
};

/**
 * Whether re-selecting the field's original pool would leave the allocated kind alone.
 * True when the picker asks for no particular kind, or asks for the one the field already
 * holds — in both cases there is nothing new to allocate.
 */
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
      // The kind is the exception: the form sends no reservation identifier, so asking
      // the same pool for a different kind is a legitimate fresh allocation and must
      // fall through instead of silently reverting to the old-kind value.
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
          // The concrete kind to allocate for a generic peer. Kept in the value (not the
          // source) because, unlike `defaultPrefixLength`, it is sent to the API.
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
      // The kind is the exception: the form sends no reservation identifier, so asking
      // the same pool for a different kind is a legitimate fresh allocation and must
      // fall through instead of silently reverting to the old-kind value.
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
          // The concrete kind to allocate for a generic peer. Kept in the value (not the
          // source) because, unlike `defaultPrefixLength`, it is sent to the API.
          ...(newValue.from_pool.allocatedKind !== undefined && {
            allocatedKind: newValue.from_pool.allocatedKind,
          }),
        },
      },
    };
  }

  return updateFormFieldValue(newValue, defaultValue) as FormRelationshipValue;
};
