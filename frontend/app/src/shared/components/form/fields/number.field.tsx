import { useState } from "react";
import { useFormContext } from "react-hook-form";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import {
  FieldTabs,
  FieldTabsContent,
  FieldTabsList,
  FieldTabsTrigger,
} from "@/shared/components/form/field-tabs";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { usePreventScrollOnNumberInput } from "@/shared/components/form/fields/usePreventScrollOnNumber";
import { PoolAllocationPanel } from "@/shared/components/form/pool-allocation-panel";
import type { DynamicNumberFieldProps, FormAttributeValue } from "@/shared/components/form/type";
import {
  updateAttributeFieldValue,
  updateFormFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, type InputProps } from "@/shared/components/ui/input";

export interface NumberFieldProps
  extends Omit<DynamicNumberFieldProps, "type" | "onChange">,
    Omit<InputProps, "defaultValue" | "name"> {}

const VALUE_TAB = "value";
const POOL_TAB = "from-pool";
type FieldTab = typeof VALUE_TAB | typeof POOL_TAB;

const NumberField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  pool,
  shouldUnregister,
  ...props
}: NumberFieldProps) => {
  const numRef = usePreventScrollOnNumberInput();
  const form = useFormContext();

  const [activeTab, setActiveTab] = useState<FieldTab>(VALUE_TAB);

  // Switching tabs abandons whatever was staged under the old one, so the field goes back
  // to the value it had on open — not to empty. That makes merely looking at the other tab
  // a no-op: `getUpdateMutationFromFormData` skips a field that deep-equals its default, so
  // nothing is submitted and an existing value is never silently cleared.
  const handleTabChange = (tab: string) => {
    setActiveTab(tab === POOL_TAB ? POOL_TAB : VALUE_TAB);
    form.setValue(name, defaultValue ?? DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
  };

  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;
        const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

        const valuePanel = (
          <>
            <FormInput>
              <Input
                {...field}
                ref={numRef}
                type="number"
                value={typeof fieldData?.value === "number" ? fieldData.value : ""}
                onChange={(event) => {
                  const value = event.target.valueAsNumber;
                  field.onChange(updateFormFieldValue(isNaN(value) ? null : value, defaultValue));
                }}
                {...props}
              />
            </FormInput>

            <FormMessage />
          </>
        );

        // Rendered inside the field so it can carry `fieldData`: that is what puts the
        // provenance badge (pool / profile / template) beside the label.
        const fieldLabel = (
          <LabelFormField
            label={label}
            unique={unique}
            required={!!rules?.required}
            description={description}
            fieldData={fieldData}
          />
        );

        if (!pool) {
          return (
            <div className="space-y-2">
              {fieldLabel}
              {valuePanel}
            </div>
          );
        }

        return (
          <FieldTabs
            value={activeTab}
            onValueChange={handleTabChange}
            // Switching discards the staged value, so it must take a deliberate press rather
            // than merely arrowing across the strip.
            activationMode="manual"
            // The label is a child of the tab root so it can carry `fieldData`; the root adds
            // no spacing of its own, so give it the same rhythm the untabbed fields use or the
            // label sits flush against the strip.
            className="space-y-2"
          >
            {fieldLabel}

            <FieldTabsList>
              <FieldTabsTrigger value={VALUE_TAB} disabled={props.disabled}>
                Value
              </FieldTabsTrigger>
              <FieldTabsTrigger value={POOL_TAB} disabled={props.disabled}>
                From pool
              </FieldTabsTrigger>
            </FieldTabsList>

            <FieldTabsContent value={VALUE_TAB}>{valuePanel}</FieldTabsContent>

            <FieldTabsContent value={POOL_TAB}>
              <PoolAllocationPanel
                name={name}
                poolKind={pool.kind}
                poolDefaultAllocatedObjectKind={pool.defaultAllocatedObjectKind}
                // Neither override applies to a number pool: it has no mask, and the value it
                // allocates is a number rather than an object with a kind. Both controls
                // withhold themselves, so the panel is the pool alone.
                options={pool.options}
                selectedPoolId={selectedPoolId}
                value={fieldData}
                disabled={props.disabled}
                onChange={(value) => field.onChange(updateAttributeFieldValue(value, defaultValue))}
              />
            </FieldTabsContent>
          </FieldTabs>
        );
      }}
    />
  );
};

export default NumberField;
