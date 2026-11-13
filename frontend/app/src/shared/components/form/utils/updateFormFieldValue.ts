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

/** The number a number pool value reserves, or null when it lets the pool pick one. */
export const getPoolNumber = (value?: FormAttributeValue): number | null => {
  if (value?.source?.type !== "pool") return null;
  const poolValue = value.value;
  if (!poolValue || typeof poolValue !== "object" || !("from_pool" in poolValue)) return null;
  return typeof poolValue.from_pool.number === "number" ? poolValue.from_pool.number : null;
};

/**
 * The number a newly picked number pool reserves: the one staged in the pool tab, else the one the
 * node holds. A schema, profile or template default is not the node's own, so the pool picks.
 */
const getNumberToReserve = (
  current: FormAttributeValue,
  defaultValue?: FormAttributeValue
): number | null => {
  const staged = getPoolNumber(current);
  if (staged !== null) return staged;

  if (defaultValue?.source?.type === "user" && typeof defaultValue.value === "number") {
    return defaultValue.value;
  }
  return getPoolNumber(defaultValue);
};

export const updateNumberPoolFieldValue = (
  newValue: PoolValue | null,
  current: FormAttributeValue,
  defaultValue?: FormAttributeValue
): FormAttributeValue => {
  const next = updateAttributeFieldValue(newValue, defaultValue);
  // The number input writes into the stored value in place, so it must never hold the default itself.
  if (next === defaultValue) return structuredClone(next);
  if (next.source?.type !== "pool") return next;

  const number = getNumberToReserve(current, defaultValue);
  if (number === null) return next;

  const { from_pool } = (next as AttributeValueFromPool).value;
  return { source: next.source, value: { from_pool: { ...from_pool, number } } };
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
      // Re-selecting the field's original pool restores the existing allocation unchanged.
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
          ...(newValue.from_pool.allocatedKind !== undefined && {
            allocatedKind: newValue.from_pool.allocatedKind,
          }),
        },
      },
    };
  }

  return updateFormFieldValue(newValue, defaultValue) as FormRelationshipValue;
};
