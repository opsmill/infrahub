import { MarkdownEditor } from "@/components/editor";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormAttributeValue, FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";

const TextareaField = ({
  defaultValue,
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
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

        return (
          <div className="relative flex flex-col">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <FormInput>
              <MarkdownEditor
                {...field}
                {...props}
                defaultValue={defaultValue?.value as string | undefined}
                onChange={(newValue) => {
                  field.onChange(updateFormFieldValue(newValue, defaultValue));
                }}
                className="w-full"
              />
            </FormInput>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default TextareaField;
