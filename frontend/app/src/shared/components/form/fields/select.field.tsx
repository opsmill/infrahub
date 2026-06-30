import { Label, Select, SelectItem, SelectList, SelectTrigger } from "@infrahub/ui";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { ResetAction } from "@/shared/components/form/fields/common";
import type {
  DynamicSelectFieldProps,
  FormAttributeValue,
  FormFieldProps,
} from "@/shared/components/form/type";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

export interface SelectFieldProps
  extends FormFieldProps,
    Omit<DynamicSelectFieldProps, "defaultValue" | "name" | "type"> {
  /** Extra classes for the field's own label (e.g. `sr-only` to hide it visually). */
  labelClassName?: string;
  /** Forwarded to the trigger so a hint/example can be announced by screen readers. */
  "aria-describedby"?: string;
}

export function SelectField({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  isBulkUpdate,
  description,
  label,
  labelClassName,
  name,
  rules,
  unique,
  items,
  shouldUnregister,
  "aria-describedby": ariaDescribedBy,
  ...props
}: SelectFieldProps) {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      shouldUnregister={shouldUnregister}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;
        const currentSelected = (fieldData?.value as string | undefined) ?? null;

        return (
          <div className="space-y-2">
            <FormInput>
              <Select
                {...props}
                value={currentSelected}
                onChange={(newSelected) => {
                  field.onChange(
                    updateFormFieldValue(
                      currentSelected === newSelected ? null : newSelected,
                      defaultValue
                    )
                  );
                }}
                placeholder=""
              >
                <Label className={labelClassName}>{label}</Label>
                <SelectTrigger aria-describedby={ariaDescribedBy} />

                <SelectList items={items}>
                  {(item) => (
                    <SelectItem key={item.key} textValue={item.label}>
                      {item.label}
                    </SelectItem>
                  )}
                </SelectList>
              </Select>
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
}
