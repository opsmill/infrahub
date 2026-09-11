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
  /** Every kind the allocation may target. Empty for a concrete peer, which pins the kind. */
  allocatableKinds?: Array<PoolKindOption>;
  selectedPoolId: string | null;
  value: FormFieldValue;
  disabled?: boolean;
  onChange: (value: PoolValue | null) => void;
}

/**
 * The "From pool" tab of every pool-backed field: which pool to allocate from, and the two
 * overrides of that pool's defaults.
 *
 * This tab *stages* a new allocation; it never displays a resolved one. Once an allocation
 * resolves the field holds a real object, so the value tab shows it and the label badges the
 * pool — which is why no field opens here, even when its value came from a pool.
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
  // A template allocates through `<name>_from_resource_pool`, typed as a plain RelatedNodeInput,
  // which carries neither override — offering them would promise what the save drops. IFC-3135.
  const canOverrideAllocation = !fromPoolRelationshipName;

  return (
    <Col className="gap-4">
      {/* Unlabelled on purpose: the tab and the placeholder already name it, and a label here
          would sit directly beneath the field's own. Only the optional overrides are labelled. */}
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

      {/* Each override hides itself when it does not apply, so the row can end up empty — and an
          empty flex item still takes the parent's `gap-4`. `empty:hidden` removes the hole. */}
      {canOverrideAllocation && (
        <Row className="items-start gap-4 empty:hidden">
          <PoolPrefixLengthField
            name={name}
            poolKind={poolKind}
            value={value}
            disabled={disabled}
            // 112px: the label plus its help button measures ~105px and wraps rather than
            // truncating, so anything narrower puts the "?" on its own line.
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
