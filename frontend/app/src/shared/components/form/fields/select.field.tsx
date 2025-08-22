import { Label } from "@/shared/components/aria/label";
import { Select, SelectItem, SelectList, SelectTrigger } from "@/shared/components/aria/select";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import {
  DynamicSelectFieldProps,
  FormAttributeValue,
  FormFieldProps,
} from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { ResetAction } from "./common";

export interface SelectFieldProps
  extends FormFieldProps,
    Omit<DynamicSelectFieldProps, "defaultValue" | "name" | "type"> {}

export function SelectField({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  attribute,
  isBulkUpdate,
  description,
  label,
  name,
  rules,
  unique,
  items,
  ...props
}: SelectFieldProps) {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;
        const currentSelectedKey = (fieldData?.value as string | undefined) ?? null;

        return (
          <div className="space-y-2">
            <FormInput>
              <Select
                selectedKey={currentSelectedKey}
                onSelectionChange={(key) =>
                  field.onChange(
                    updateFormFieldValue(currentSelectedKey === key ? null : key, defaultValue)
                  )
                }
                placeholder=""
                {...props}
              >
                <Label>{label}</Label>
                <SelectTrigger />

                <SelectList selectionMode="single" items={items}>
                  {(item) => <SelectItem textValue={item.label}>{item.label}</SelectItem>}
                </SelectList>
              </Select>
            </FormInput>

            {isBulkUpdate && attribute.optional && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
    />
  );
}
