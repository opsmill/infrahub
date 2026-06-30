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
  NUMBER_POOL_KIND,
} from "@/entities/resource-manager/constants";
import { validateNumberAttribute } from "@/entities/schema/utils/validation/validate-number-attribute";

// Pool default, injected into the relationship query (module-level for a stable cache key).
const POOL_ADDITIONAL_FIELDS = { default_prefix_length: { value: true } };

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

  // The prefix-length override only applies to a pending allocation, for IP pools.
  const pendingFromPool =
    value.source?.type === "pool" &&
    value.value &&
    typeof value.value === "object" &&
    "from_pool" in value.value
      ? value.value.from_pool
      : null;
  const showPrefixLength =
    !!pendingFromPool && (poolKind === IP_ADDRESS_POOL || poolKind === IP_PREFIX_POOL);

  // Pool default, shown as the override placeholder (carried on the source, no extra fetch).
  const defaultPrefixLength =
    value.source?.type === "pool" && value.source.kind !== NUMBER_POOL_KIND
      ? value.source.defaultPrefixLength
      : null;

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
              placeholder={defaultPrefixLength == null ? undefined : String(defaultPrefixLength)}
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
              // Re-selecting the current pool is a no-op (clear via the input or reset action).
              if (selectedPoolId !== pool.id) {
                onChange({
                  from_pool: {
                    id: pool.id,
                    name: pool.display_label,
                    kind: pool.__typename,
                    defaultPrefixLength: pool.default_prefix_length?.value ?? null,
                  },
                });
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
