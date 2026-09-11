import { useState } from "react";
import { useFormContext } from "react-hook-form";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import {
  FieldTabs,
  FieldTabsContent,
  FieldTabsList,
  FieldTabsTrigger,
} from "@/shared/components/form/field-tabs";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import { PoolAllocationPanel } from "@/shared/components/form/pool-allocation-panel";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import {
  updateAttributeFieldValue,
  updateFormFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, type InputProps } from "@/shared/components/ui/input";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name" | "onChange"> {}

const VALUE_TAB = "value";
const POOL_TAB = "from-pool";
type FieldTab = typeof VALUE_TAB | typeof POOL_TAB;

const InputField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  description,
  label,
  name,
  rules,
  unique,
  pool,
  isBulkUpdate,
  shouldUnregister,
  autoFocus,
  ...props
}: InputFieldProps) => {
  const form = useFormContext();

  const [activeTab, setActiveTab] = useState<FieldTab>(VALUE_TAB);

  // Switching tabs abandons whatever was staged under the old one, so the field goes back to
  // the value it had on open — not to empty. That makes merely looking at the other tab a
  // no-op: `getUpdateMutationFromFormData` skips a field that deep-equals its default, so
  // nothing is submitted and an existing value is never silently cleared. It also stops the
  // nested `${name}.value.from_pool.*` fields surviving a switch.
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

        // Anything the text input cannot show — a from-pool marker, a list — renders empty
        // rather than being asserted into a string.
        const inputValue =
          typeof fieldData?.value === "string" || typeof fieldData?.value === "number"
            ? String(fieldData.value)
            : "";

        const valuePanel = (
          <>
            <FormInput>
              <Input
                {...field}
                {...props}
                value={inputValue}
                onChange={(event) => {
                  field.onChange(updateFormFieldValue(event.target.value, defaultValue));
                }}
                autoFocus={autoFocus}
              />
            </FormInput>

            {!props.disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

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
                // No `allocatableKinds`: an `address`/`prefix` attribute pins the kind to the
                // node being created, so there is nothing to override.
                options={pool.options}
                fromPoolRelationshipName={pool.fromPoolRelationshipName}
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

export default InputField;
