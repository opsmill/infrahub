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
  // Shown as the prefix-length placeholder so the user sees what the pool would
  // allocate by default. The override is only sent when the user types a value.
  const [defaultPrefixLength, setDefaultPrefixLength] = React.useState<number | null>(null);

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

  // The prefix-length override only applies to a pending IP address allocation (a
  // resolved address can't be re-allocated with a new mask). It is its own form field,
  // nested at the allocation's `from_pool.prefixlen`, so it owns its validation/error.
  //
  // Address pools only: the IP prefix pool from-pool input takes `size`, not
  // `prefixlen`, so offering this field for prefix pools would send a value the API
  // rejects. Supporting prefix pools is a separate enhancement.
  const pendingFromPool =
    value.source?.type === "pool" &&
    value.value &&
    typeof value.value === "object" &&
    "from_pool" in value.value
      ? value.value.from_pool
      : null;
  const showPrefixLength = !!pendingFromPool && poolKind === IP_ADDRESS_POOL;

  return (
    <>
      {/* Sits between the value input and the pool button. */}
      {showPrefixLength && (
        <FormField
          name={`${name}.value.from_pool.prefixlen`}
          rules={{
            validate: (prefixlen: number | null | undefined) => {
              const result = validateNumberAttribute(
                { min: MIN_PREFIX_LENGTH, max: MAX_PREFIX_LENGTH },
                prefixlen ?? null
              );
              return result.success || result.error;
            },
          }}
          render={({ field, fieldState }) => (
            <PoolPrefixLengthInput
              value={field.value}
              placeholder={defaultPrefixLength}
              invalid={!!fieldState.error}
              onChange={field.onChange}
            />
          )}
        />
      )}

      <Combobox open={isOpen} onOpenChange={setIsOpen}>
        <PoolPopoverTrigger data-testid="select-open-pool-option-button" />

        <ComboboxContent align="end" fitTriggerWidth={false}>
          <RelationshipComboboxList
            onSelect={(pool) => {
              // Re-selecting the already-selected pool is a no-op: keep the current
              // value rather than clearing it. Clearing a pool is done through the
              // relationship/attribute input or the reset action.
              if (selectedPoolId !== pool.id) {
                setDefaultPrefixLength(pool.default_prefix_length?.value ?? null);
                onChange({
                  from_pool: {
                    id: pool.id,
                    name: pool.display_label,
                    kind: pool.__typename,
                    // No prefixlen here: only the override the user explicitly types is sent.
                    // Allocation is idempotent — re-selecting a pool that already holds a
                    // reservation for this object can't change the mask, and the backend
                    // rejects a conflicting prefix length. Omitting it on the zero-effort path
                    // keeps that case working (the existing reservation is reused).
                    //
                    // This is a workaround for that edge case. The cleaner fix is a dedicated
                    // endpoint to look up a pool's reserved resources, so this field could show
                    // the already-reserved prefix and disable editing instead of relying on a
                    // backend error.
                  },
                });
              }
              setIsOpen(false);
            }}
            peer={poolKind}
            selectedValue={selectedPoolId ?? undefined}
            filterQuery={filterQuery}
          />
        </ComboboxContent>
      </Combobox>
    </>
  );
}
