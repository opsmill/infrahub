import React from "react";

import { PoolPrefixLengthInput } from "@/shared/components/form/pool-prefix-length-input";
import { PoolPopoverTrigger, type PoolValue } from "@/shared/components/form/pool-selector";
import type { FormFieldValue } from "@/shared/components/form/type";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { FormField } from "@/shared/components/ui/form";

import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import {
  IP_ADDRESS_POOL,
  IP_PREFIX_POOL,
  MAX_PREFIX_LENGTH,
  MIN_PREFIX_LENGTH,
} from "@/entities/resource-manager/constants";
import { validateNumberAttribute } from "@/entities/schema/utils/validation/validate-number-attribute";

// Both IP pool kinds expose default_prefix_length; we surface it as the placeholder on
// the prefix-length override. Injected into the relationship list query so the generic
// builder stays kind-agnostic. Module-level for a stable react-query cache key.
const POOL_ADDITIONAL_FIELDS = { default_prefix_length: { value: true } };

// The extra node field POOL_ADDITIONAL_FIELDS requests, typed for the combobox callbacks.
type PoolNodeFields = { default_prefix_length?: { value?: number | null } | null };

export interface PoolSelectProps {
  /** Name of the host form field; used to register the nested prefix-length field. */
  name: string;
  poolKind: string;
  poolDefaultAllocatedObjectKind: string;
  selectedPoolId: string | null;
  value: FormFieldValue;
  onChange: (value: PoolValue | null) => void;
}

export function PoolSelect({
  name,
  poolDefaultAllocatedObjectKind,
  poolKind,
  onChange,
  selectedPoolId,
  value,
}: PoolSelectProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  const filterQuery = React.useMemo<
    { default_address_type__value: string } | { default_prefix_type__value: string } | undefined
  >(() => {
    switch (poolKind) {
      case IP_ADDRESS_POOL: {
        return {
          default_address_type__value: poolDefaultAllocatedObjectKind,
        };
      }
      case IP_PREFIX_POOL: {
        return {
          default_prefix_type__value: poolDefaultAllocatedObjectKind,
        };
      }
      default: {
        return;
      }
    }
  }, [poolKind, poolDefaultAllocatedObjectKind]);

  // The prefix-length override only applies to a pending allocation (a resolved value
  // can't be re-allocated with a new mask). It is its own form field, nested at the
  // allocation's `from_pool.prefixLength`, so it owns its validation/error.
  //
  // Offered for both IP address pools (sets the new address's mask) and IP prefix pools
  // (sets the size of the carved-out subnet); both map to the allocation's prefix length.
  const pendingFromPool =
    value.source?.type === "pool" &&
    value.value &&
    typeof value.value === "object" &&
    "from_pool" in value.value
      ? value.value.from_pool
      : null;
  const showPrefixLength =
    !!pendingFromPool && (poolKind === IP_ADDRESS_POOL || poolKind === IP_PREFIX_POOL);

  // The pool's default prefix length is shown as a placeholder so the user can see which
  // mask a blank override will allocate. It is captured from the pool option at selection
  // time and carried on the field's source, so no extra fetch is needed here.
  const defaultPrefixLength =
    value.source?.type === "pool" ? value.source.defaultPrefixLength : null;

  return (
    <>
      {/* Sits between the value input and the pool button. */}
      {showPrefixLength && (
        <FormField
          name={`${name}.value.from_pool.prefixLength`}
          rules={{
            validate: (prefixLength: number | null | undefined) => {
              if (typeof prefixLength === "number" && !Number.isInteger(prefixLength)) {
                return "Prefix length must be a whole number";
              }
              const result = validateNumberAttribute(
                { min: MIN_PREFIX_LENGTH, max: MAX_PREFIX_LENGTH },
                prefixLength ?? null
              );
              return result.success || result.error;
            },
          }}
          render={({ field, fieldState }) => (
            <PoolPrefixLengthInput
              value={field.value}
              invalid={!!fieldState.error}
              placeholder={defaultPrefixLength}
              onChange={field.onChange}
            />
          )}
        />
      )}

      <Combobox open={isOpen} onOpenChange={setIsOpen}>
        <PoolPopoverTrigger data-testid="select-open-pool-option-button" />

        <ComboboxContent align="end" fitTriggerWidth={false}>
          <RelationshipComboboxList<PoolNodeFields>
            onSelect={(pool) => {
              // Re-selecting the already-selected pool is a no-op: keep the current
              // value rather than clearing it. Clearing a pool is done through the
              // relationship/attribute input or the reset action.
              if (selectedPoolId !== pool.id) {
                onChange({
                  from_pool: {
                    id: pool.id,
                    name: pool.display_label,
                    kind: pool.__typename,
                    defaultPrefixLength: pool.default_prefix_length?.value ?? null,
                  },
                });
                // No prefixLength is sent unless the user types an override: allocation is
                // idempotent, so re-selecting a pool that already holds a reservation can't
                // change the mask, and the backend rejects a conflicting length.
              }
              setIsOpen(false);
            }}
            peer={poolKind}
            selectedValue={selectedPoolId ?? undefined}
            filterQuery={filterQuery}
            additionalFields={POOL_ADDITIONAL_FIELDS}
          />
        </ComboboxContent>
      </Combobox>
    </>
  );
}
