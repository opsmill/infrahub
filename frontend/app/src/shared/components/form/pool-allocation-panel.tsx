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
 * The "From pool" tab: which pool to allocate from, plus the two overrides of that pool's
 * defaults. It stages a new allocation and never displays a resolved one.
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
  // `<name>_from_resource_pool` is a plain RelatedNodeInput carrying neither override, so
  // offering them would promise what the save drops.
  const canOverrideAllocation = !fromPoolRelationshipName;

  return (
    <Col className="gap-4">
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

      {/* An override that hides itself leaves an empty flex item still taking the parent's gap; `empty:hidden` removes the hole. */}
      {canOverrideAllocation && (
        <Row className="items-start gap-4 empty:hidden">
          <PoolPrefixLengthField
            name={name}
            poolKind={poolKind}
            value={value}
            disabled={disabled}
            // 112px: the label plus its help button measures ~105px and wraps below that.
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
