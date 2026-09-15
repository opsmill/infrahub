import React from "react";

import { Col, Row } from "@/shared/components/container";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { type PoolKindOption, PoolKindSelect } from "@/shared/components/form/pool-kind-select";
import { PoolPrefixLengthInput } from "@/shared/components/form/pool-prefix-length-input";
import type { FormFieldValue, PoolValue } from "@/shared/components/form/type";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormField } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import {
  IP_ADDRESS_POOL,
  IP_PREFIX_POOL,
  MAX_PREFIX_LENGTH,
  MIN_PREFIX_LENGTH,
  NUMBER_POOL_KIND,
} from "@/entities/resource-manager/domain/model/pool";
import { validateNumberAttribute } from "@/entities/schema/domain/rules/validation/validate-number-attribute";

/**
 * Pool defaults injected into the relationship query, keyed by pool kind because
 * `default_address_type` and `default_prefix_type` each exist on only one of the two IP pool
 * types — selecting both would make the query invalid against either. Module-level so the
 * object identity, and with it the query cache key, stays stable.
 */
const ADDRESS_POOL_ADDITIONAL_FIELDS = {
  default_prefix_length: { value: true },
  default_address_type: { value: true },
};
const PREFIX_POOL_ADDITIONAL_FIELDS = {
  default_prefix_length: { value: true },
  default_prefix_type: { value: true },
};

function getPoolAdditionalFields(poolKind: string): Record<string, unknown> | undefined {
  switch (poolKind) {
    case IP_ADDRESS_POOL:
      return ADDRESS_POOL_ADDITIONAL_FIELDS;
    case IP_PREFIX_POOL:
      return PREFIX_POOL_ADDITIONAL_FIELDS;
    default:
      return undefined;
  }
}

type PoolNodeFields = {
  default_prefix_length?: { value?: number | null } | null;
  default_address_type?: { value?: string | null } | null;
  default_prefix_type?: { value?: string | null } | null;
};

type PoolFilterQuery =
  | { default_address_type__value: string }
  | { default_prefix_type__value: string }
  | { default_address_type__values: string[] }
  | { default_prefix_type__values: string[] }
  | undefined;

/**
 * Non-IP pools are not filtered by allocated kind at all. For IP pools the plural `__values`
 * filter applies whenever the caller knows the full set of allocatable kinds (see
 * `allocatableKinds`); the singular `__value` filter is the concrete-peer case, where the
 * relationship pins the allocation to one kind.
 */
function getPoolFilterQuery(
  poolKind: string,
  poolDefaultAllocatedObjectKind: string,
  allocatableKinds: string[] | undefined
): PoolFilterQuery {
  switch (poolKind) {
    case IP_ADDRESS_POOL:
      return allocatableKinds?.length
        ? { default_address_type__values: allocatableKinds }
        : { default_address_type__value: poolDefaultAllocatedObjectKind };
    case IP_PREFIX_POOL:
      return allocatableKinds?.length
        ? { default_prefix_type__values: allocatableKinds }
        : { default_prefix_type__value: poolDefaultAllocatedObjectKind };
    default:
      return undefined;
  }
}

const isIpPool = (poolKind: string) => poolKind === IP_ADDRESS_POOL || poolKind === IP_PREFIX_POOL;

/**
 * The `from_pool` marker of an allocation still awaiting the API, or `null` when the field
 * holds anything else — a resolved node, a plain value, nothing. Both overrides only ever
 * apply to a pending allocation: a resolved one cannot be re-cut.
 */
function getPendingFromPool(value: FormFieldValue) {
  return value.source?.type === "pool" &&
    value.value &&
    typeof value.value === "object" &&
    "from_pool" in value.value
    ? value.value.from_pool
    : null;
}

export interface PoolComboboxProps {
  poolKind: string;
  poolDefaultAllocatedObjectKind: string;
  /**
   * Every kind the peer generic is implemented by. When set, the pool list is filtered over
   * the whole set rather than pinned to one kind: `poolDefaultAllocatedObjectKind` is the
   * generic itself for a generic peer (no pool defaults to it), and filtering by the kind
   * the user selected would hide pools that default to a sibling kind — exactly the pools
   * this feature exists to allocate from.
   */
  allocatableKinds?: string[];
  /**
   * Pools to offer instead of querying for them; see `FormFieldPool.options`. A number pool
   * belongs to one node kind and one attribute, a narrowing only the field builder can make,
   * so those arrive pre-fetched.
   */
  options?: Array<NodeCore>;
  selectedPoolId: string | null;
  value: FormFieldValue;
  disabled?: boolean;
  /** Ties a caller's visible label to the trigger. */
  id?: string;
  onChange: (value: PoolValue | null) => void;
}

/**
 * Picks the pool an allocation is cut from, as the "From pool" panel's own value: the trigger
 * spans the panel and names the selected pool itself. Renders no layout of its own.
 */
export function PoolCombobox({
  poolDefaultAllocatedObjectKind,
  poolKind,
  allocatableKinds,
  options,
  disabled,
  id,
  onChange,
  selectedPoolId,
  value,
}: PoolComboboxProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  const filterQuery = getPoolFilterQuery(
    poolKind,
    poolDefaultAllocatedObjectKind,
    allocatableKinds
  );

  // The pool's name rides on the source, so the trigger names it without a second fetch.
  const selectedPoolLabel = value.source?.type === "pool" ? value.source.label : null;

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger
        id={id}
        disabled={disabled}
        aria-label="Pool"
        // The panel shows no "Pool" label — the tab already names it — so the one piece of
        // non-obvious information, that nothing is allocated until the form is saved, rides
        // here rather than in a label description.
        title="Pool to allocate from when the form is saved"
        className="cursor-pointer"
        data-testid="select-open-pool-option-button"
      >
        {selectedPoolLabel ? (
          <span data-testid="select-value">{selectedPoolLabel}</span>
        ) : (
          <span className="text-subtle-muted">Select a pool</span>
        )}
      </ComboboxTrigger>

      <ComboboxContent align="start">
        {options ? (
          <ComboboxList>
            <ComboboxEmpty>No pools found</ComboboxEmpty>
            {options.map((pool) => {
              const poolLabel = getNodeLabel(pool);
              return (
                <ComboboxItem
                  key={pool.id}
                  value={pool.id}
                  keywords={[poolLabel, pool.id]}
                  selectedValue={selectedPoolId ?? undefined}
                  onSelect={() => {
                    // Re-selecting the current pool is a no-op; the value tab is what clears it.
                    if (selectedPoolId !== pool.id) {
                      onChange({
                        from_pool: { id: pool.id, name: poolLabel, kind: pool.__typename },
                      });
                    }
                    setIsOpen(false);
                  }}
                >
                  {poolLabel}
                </ComboboxItem>
              );
            })}
          </ComboboxList>
        ) : (
          <RelationshipComboboxList<PoolNodeFields>
            onSelect={(pool) => {
              if (selectedPoolId !== pool.id) {
                onChange({
                  from_pool: {
                    id: pool.id,
                    name: pool.display_label,
                    // The pool's own kind; the kind to allocate is `allocatedKind`, set by
                    // `PoolKindOverrideField`.
                    kind: pool.__typename,
                    defaultPrefixLength: pool.default_prefix_length?.value ?? null,
                    defaultAllocatedKind:
                      (poolKind === IP_PREFIX_POOL
                        ? pool.default_prefix_type?.value
                        : pool.default_address_type?.value) ?? null,
                  },
                });
              }
              setIsOpen(false);
            }}
            peer={poolKind}
            selectedValue={selectedPoolId ?? undefined}
            filterQuery={filterQuery}
            additionalFields={getPoolAdditionalFields(poolKind)}
          />
        )}
      </ComboboxContent>
    </Combobox>
  );
}

export interface PoolPrefixLengthFieldProps {
  /** Name of the host form field; used to register the nested prefix-length field. */
  name: string;
  poolKind: string;
  value: FormFieldValue;
  disabled?: boolean;
  className?: string;
}

/**
 * Overrides the mask of a pending from-pool allocation. Owns the whole visibility decision
 * (hence the bare `null`) so no caller has to restate it: only a pending allocation from an
 * IP pool can still be re-cut.
 */
export function PoolPrefixLengthField({
  name,
  poolKind,
  value,
  disabled,
  className,
}: PoolPrefixLengthFieldProps) {
  const id = React.useId();

  if (!getPendingFromPool(value) || !isIpPool(poolKind)) return null;

  // Pool default, shown as the override placeholder (carried on the source, no extra fetch).
  const defaultPrefixLength =
    value.source?.type === "pool" && value.source.kind !== NUMBER_POOL_KIND
      ? value.source.defaultPrefixLength
      : null;

  return (
    // gap-2 between a label and its control, matching the plain fields (`space-y-2` in
    // input.field / number.field).
    <Col className={classNames("gap-2", className)}>
      <LabelFormField
        label="Prefix length"
        description={
          defaultPrefixLength == null
            ? "Mask of the allocated prefix. Leave it as it is to keep the pool's default."
            : `This pool allocates a /${defaultPrefixLength} by default. Enter another mask to override it for this allocation, or leave it as it is to keep the pool's default.`
        }
        variant="small"
        htmlFor={id}
      />
      <FormField
        name={`${name}.value.from_pool.prefixLength`}
        // Whatever clears a from-pool allocation replaces the host field's whole value, which
        // already takes this nested value with it — so nothing leaks by opting out of the
        // unmount unregister. Opting *in* crashes: react-hook-form's `unset` walks
        // `<name>.value.from_pool` on unmount, and by then `value` is the reset `null`.
        shouldUnregister={false}
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
            id={id}
            value={field.value}
            invalid={!!fieldState.error}
            placeholder={defaultPrefixLength == null ? undefined : String(defaultPrefixLength)}
            className="w-full"
            disabled={disabled}
            onChange={field.onChange}
          />
        )}
      />
    </Col>
  );
}

export interface PoolKindOverrideFieldProps {
  /** Name of the host form field; used to register the nested allocated-kind field. */
  name: string;
  poolKind: string;
  /** Every kind the allocation may target — the peer generic's implementations. */
  options: Array<PoolKindOption>;
  value: FormFieldValue;
  disabled?: boolean;
  className?: string;
}

/**
 * Overrides the target kind of a pending from-pool allocation. Rendered *below* the pool row
 * rather than inside it, so it reads as its own control instead of another slot in the value
 * input. Owns the whole visibility decision (hence the bare `null`) so no caller has to
 * restate it: there must be a pending allocation from an IP pool, and more than one candidate
 * kind — a single-option dropdown would be no override at all.
 */
export function PoolKindOverrideField({
  name,
  poolKind,
  options,
  value,
  disabled,
  className,
}: PoolKindOverrideFieldProps) {
  const id = React.useId();

  if (!getPendingFromPool(value) || !isIpPool(poolKind) || options.length <= 1) return null;

  // Pool default, shown as the placeholder so an empty override reads as "allocate the
  // pool's own kind" (carried on the source, no extra fetch).
  const defaultAllocatedKind =
    value.source?.type === "pool" && value.source.kind !== NUMBER_POOL_KIND
      ? value.source.defaultAllocatedKind
      : null;
  const defaultOption = options.find((option) => option.kind === defaultAllocatedKind);
  const defaultKindName = defaultOption?.label ?? defaultAllocatedKind;

  // Spelled out because the control is otherwise indistinguishable from a required choice:
  // leaving it alone is legitimate and means "let the pool decide".
  const description = defaultKindName
    ? `This pool allocates a "${defaultKindName}" by default. Pick another type to override it for this allocation, or leave it as it is to keep the pool's default.`
    : "Pick the type of object to allocate, or leave it as it is to keep the pool's default.";

  return (
    // gap-2 between a label and its control, matching the plain fields (`space-y-2` in
    // input.field / number.field) so this override sits on the same rhythm.
    <Col className={classNames("gap-2", className)}>
      <LabelFormField
        label="Type to allocate"
        description={description}
        variant="small"
        htmlFor={id}
      />
      <Row>
        <FormField
          name={`${name}.value.from_pool.allocatedKind`}
          // Same as the prefix-length override: the host field's value carries this one away
          // when it is cleared, and unregistering on unmount would walk an already-null path.
          shouldUnregister={false}
          render={({ field, fieldState }) => (
            <PoolKindSelect
              id={id}
              value={field.value}
              options={options}
              placeholder={defaultOption?.label ?? defaultAllocatedKind ?? undefined}
              invalid={!!fieldState.error}
              disabled={disabled}
              onChange={field.onChange}
            />
          )}
        />
      </Row>
    </Col>
  );
}
