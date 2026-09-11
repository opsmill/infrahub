import { Col, Row } from "@/shared/components/container";
import type { PoolKindOption } from "@/shared/components/form/pool-kind-select";
import type { FormFieldPool, FormFieldValue, PoolValue } from "@/shared/components/form/type";
import {
  PoolCombobox,
  PoolKindOverrideField,
  PoolPrefixLengthField,
} from "@/shared/components/inputs/pool-select";
import { FormMessage } from "@/shared/components/ui/form";

export interface PoolAllocationPanelProps
  extends Pick<FormFieldPool, "options" | "fromPoolRelationshipName"> {
  /** Name of the host form field; the nested override fields register under it. */
  name: string;
  poolKind: string;
  poolDefaultAllocatedObjectKind: string;
  /**
   * Every kind the allocation may target — the peer generic's implementations. A concrete peer
   * leaves it empty: the kind is already pinned, so there is nothing to override.
   */
  allocatableKinds?: Array<PoolKindOption>;
  selectedPoolId: string | null;
  value: FormFieldValue;
  disabled?: boolean;
  onChange: (value: PoolValue | null) => void;
}

/**
 * The "From pool" tab of every pool-backed field: which pool to allocate from, and the two
 * per-allocation overrides of that pool's own defaults. Shared rather than restated per field so
 * the panel cannot drift apart between them.
 *
 * Note what this tab is *for*: staging a new allocation. It is not where an existing one is
 * displayed. Once an allocation resolves, the field holds a real object, so the value tab shows
 * it and the label carries a badge naming the pool it came from — which is strictly more than
 * this tab can offer, since a resolved allocation cannot be re-cut and so has no controls here.
 * That is why no field opens on this tab, even when its value came from a pool.
 *
 * No kind picker — the pool decides what it allocates unless "Type to allocate" says otherwise.
 * Both overrides own their own visibility, so a field that cannot use one simply gets a panel
 * without it (a number pool has neither).
 */
export const PoolAllocationPanel = ({
  name,
  poolKind,
  poolDefaultAllocatedObjectKind,
  allocatableKinds,
  options,
  fromPoolRelationshipName,
  selectedPoolId,
  value,
  disabled,
  onChange,
}: PoolAllocationPanelProps) => {
  // An object template submits its allocation through `<name>_from_resource_pool`, whose peer is
  // the pool kind — so GraphQL types it as a plain RelatedNodeInput carrying neither `prefixlen`
  // nor `address_type`, and `create.py` allocates from the stored pool pointer alone. Neither
  // override can reach the API on that path, so offering them would promise something the save
  // silently drops. Tracked in IFC-3135.
  const canOverrideAllocation = !fromPoolRelationshipName;

  return (
    // gap-4 between the pool and the override row, so they read as separate rows rather than
    // one block.
    <Col className="gap-4">
      {/* The pool takes a line of its own: it is the panel's value, and the overrides below
          only mean anything once one is picked.

          Deliberately unlabelled. The tab already says "From pool" and the control's own
          placeholder says "Select a pool", so a third naming of the same thing is noise — and
          it would sit directly beneath the field's label. This matches the value tab of every
          field, where the primary control is likewise unlabelled and the field's own label
          names it. Only the *overrides* below carry labels, because those are optional and not
          self-evident. The accessible name lives on the control itself. */}
      <PoolCombobox
        poolKind={poolKind}
        poolDefaultAllocatedObjectKind={poolDefaultAllocatedObjectKind}
        allocatableKinds={allocatableKinds?.map((option) => option.kind)}
        options={options}
        selectedPoolId={selectedPoolId}
        value={value}
        disabled={disabled}
        onChange={onChange}
      />

      {/* Both overrides share the next line, each labelled. The mask needs room for two or
          three digits; the type needs room for a label and its namespace badge, so it takes
          the rest. They render themselves away when they do not apply, so one may end up
          alone on the line — or neither, before a pool is picked.

          `empty:hidden` is what stops that last case leaving a hole: an empty row is still a
          flex item, so the parent's `gap-4` would reserve space beneath the pool for overrides
          that are not there. Hiding it removes it from the layout instead of duplicating each
          override's visibility rule here. */}
      {canOverrideAllocation && (
        <Row className="items-start gap-4 empty:hidden">
          <PoolPrefixLengthField
            name={name}
            poolKind={poolKind}
            value={value}
            disabled={disabled}
            // 112px: "Prefix length" plus its help button measures ~105px, and the label row
            // wraps rather than truncating, so a narrower column puts the "?" on its own line.
            className="w-28 shrink-0"
          />

          <PoolKindOverrideField
            name={name}
            poolKind={poolKind}
            options={allocatableKinds ?? []}
            value={value}
            disabled={disabled}
            className="flex-1"
          />
        </Row>
      )}

      <FormMessage />
    </Col>
  );
};
