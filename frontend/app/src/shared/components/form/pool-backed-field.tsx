import { type ReactNode, useState } from "react";
import { useFormContext } from "react-hook-form";

import { Col } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import {
  FieldTabs,
  FieldTabsContent,
  FieldTabsList,
  FieldTabsTrigger,
} from "@/shared/components/form/field-tabs";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { PoolAllocationPanel } from "@/shared/components/form/pool-allocation-panel";
import type { PoolKindOption } from "@/shared/components/form/pool-kind-select";
import type { FormFieldPool, FormFieldValue, PoolValue } from "@/shared/components/form/type";
import type { LabelProps } from "@/shared/components/ui/label";

const VALUE_TAB = "value";
const POOL_TAB = "from-pool";
type FieldTab = typeof VALUE_TAB | typeof POOL_TAB;

export interface PoolBackedFieldProps {
  name: string;
  label?: string;
  description?: string | null;
  unique?: boolean;
  required?: boolean;
  labelVariant?: LabelProps["variant"];
  fieldData: FormFieldValue;
  defaultValue?: FormFieldValue;
  /** Absence of a pool is the single gate on the tabs: without one the field renders untabbed. */
  pool?: FormFieldPool;
  /** Every kind the allocation may target. Omitted when the field pins the kind. */
  allocatableKinds?: Array<PoolKindOption>;
  valueTabLabel: "Value" | "Object";
  disabled?: boolean;
  untabbedClassName?: string;
  onPoolChange: (value: PoolValue | null) => void;
  onTabSwitch?: () => void;
  children: ReactNode;
}

/**
 * A field satisfied either by a value the user supplies or by an allocation from a resource pool,
 * offered as two tabs. Given no pool it renders the value alone, untabbed. The label badges where
 * the current value came from; switching tabs discards whatever the other one staged.
 */
export const PoolBackedField = ({
  name,
  label,
  description,
  unique,
  required,
  labelVariant,
  fieldData,
  defaultValue,
  pool,
  allocatableKinds,
  valueTabLabel,
  disabled,
  untabbedClassName,
  onPoolChange,
  onTabSwitch,
  children,
}: PoolBackedFieldProps) => {
  const form = useFormContext();
  const [activeTab, setActiveTab] = useState<FieldTab>(VALUE_TAB);

  // Restoring the default rather than emptying leaves the field out of the mutation, so merely
  // visiting the other tab is a no-op.
  const handleTabChange = (tab: string) => {
    setActiveTab(tab === POOL_TAB ? POOL_TAB : VALUE_TAB);
    form.setValue(name, defaultValue ?? DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
    onTabSwitch?.();
  };

  const fieldLabel = (
    <LabelFormField
      label={label}
      unique={unique}
      required={required}
      description={description}
      variant={labelVariant}
      fieldData={fieldData}
    />
  );

  if (!pool) {
    return (
      <Col>
        {fieldLabel}
        <Col className={untabbedClassName}>{children}</Col>
      </Col>
    );
  }

  const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

  return (
    <FieldTabs
      value={activeTab}
      onValueChange={handleTabChange}
      // Switching discards the staged value, so it must take a press rather than an arrow key.
      activationMode="manual"
    >
      {fieldLabel}

      <FieldTabsList>
        <FieldTabsTrigger value={VALUE_TAB} disabled={disabled}>
          {valueTabLabel}
        </FieldTabsTrigger>
        <FieldTabsTrigger value={POOL_TAB} disabled={disabled}>
          From pool
        </FieldTabsTrigger>
      </FieldTabsList>

      <FieldTabsContent value={VALUE_TAB}>{children}</FieldTabsContent>

      <FieldTabsContent value={POOL_TAB}>
        <PoolAllocationPanel
          name={name}
          poolKind={pool.kind}
          poolDefaultAllocatedObjectKind={pool.defaultAllocatedObjectKind}
          allocatableKinds={allocatableKinds}
          options={pool.options}
          fromPoolRelationshipName={pool.fromPoolRelationshipName}
          selectedPoolId={selectedPoolId}
          value={fieldData}
          disabled={disabled}
          onChange={onPoolChange}
        />
      </FieldTabsContent>
    </FieldTabs>
  );
};
