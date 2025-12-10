import { formatISO } from "date-fns";
import type { ComponentProps } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField, ResetAction } from "@/shared/components/form/fields/common";
import type { FormAttributeValue, FormFieldProps } from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { DatePicker } from "@/shared/components/inputs/date-picker";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface DatetimeFieldProps
  extends FormFieldProps,
    Omit<ComponentProps<typeof DatePicker>, "defaultValue" | "name"> {}

const DatetimeField = ({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  deprecation,
  isBulkUpdate,
  attribute,
  description,
  label,
  name,
  rules,
  unique,
  shouldUnregister,
  ...props
}: DatetimeFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        const handleChange = (newDate: Date) => {
          const newDateValue = formatISO(newDate);
          field.onChange(updateFormFieldValue(newDateValue, defaultValue));
        };

        return (
          <div className="space-y-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              deprecation={deprecation}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              <DatePicker
                {...field}
                date={fieldData?.value ? new Date(fieldData.value as string) : null}
                onChange={handleChange}
                {...props}
              />
            </FormInput>

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

export default DatetimeField;
