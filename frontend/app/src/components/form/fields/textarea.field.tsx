import { MarkdownEditor } from "@/components/editor";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormAttributeValue, FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import {classNames} from "@/utils/common";

const TextareaField = ({
  defaultValue = { source: null, value: null },
  description,
  label,
  name,
  rules,
  unique,
  ...props
}: FormFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field, fieldState}) => {
        const fieldData: FormAttributeValue = field.value;
        const { error } =fieldState;

        return (
          <div>
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
              className="mb-2"
            />

            <FormInput className={classNames("w-full", error && "border-red-500 focus-within:border-red-500 focus-within:outline-red-500")}>
              <MarkdownEditor
                {...field}
                {...props}
                defaultValue={defaultValue?.value as string | undefined}
                value={fieldData?.value as string | undefined}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
              />
            </FormInput>

            <FormMessage className="mt-2" />
          </div>
        );
      }}
    />
  );
};

export default TextareaField;
