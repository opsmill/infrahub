import React from "react";
import { Button } from "react-aria-components";

import { Row } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import {
  updateAttributeFieldValue,
  updateFormFieldValue,
} from "@/shared/components/form/utils/updateFormFieldValue";
import { PoolSelect } from "@/shared/components/inputs/pool-select";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input, type InputProps } from "@/shared/components/ui/input";
import { inputStyle } from "@/shared/components/ui/style";

export interface InputFieldProps
  extends FormFieldProps,
    Omit<InputProps, "defaultValue" | "name" | "onChange"> {}

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
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const [override, setOverride] = React.useState(false);
        const fieldData: FormAttributeValue = field.value;
        const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

        return (
          <div className="space-y-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <Row className="gap-1">
              <FormInput>
                {!selectedPoolId || override ? (
                  <Input
                    {...field}
                    {...props}
                    value={selectedPoolId ? "" : ((fieldData?.value as string) ?? "")}
                    onChange={(event) => {
                      field.onChange(updateFormFieldValue(event.target.value, defaultValue));
                    }}
                    autoFocus={autoFocus || override}
                    onBlur={() => setOverride(false)}
                  />
                ) : (
                  <Button className={inputStyle} onPress={() => setOverride(true)}>
                    Allocated by pool
                  </Button>
                )}
              </FormInput>

              {pool && (
                <PoolSelect
                  poolKind={pool.kind}
                  poolDefaultAllocatedObjectKind={pool.defaultAllocatedObjectKind}
                  selectedPoolId={selectedPoolId}
                  onChange={(value) =>
                    field.onChange(updateAttributeFieldValue(value, defaultValue))
                  }
                />
              )}
            </Row>

            {!props.disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default InputField;
