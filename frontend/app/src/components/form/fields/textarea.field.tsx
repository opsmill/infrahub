import { MarkdownEditor } from "@/components/editor";
import { LabelFormField } from "@/components/form/fields/common";
import { FormAttributeValue, FormFieldProps } from "@/components/form/type";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { classNames } from "@/utils/common";

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
      render={({ field }) => {
        const fieldData: FormAttributeValue = field.value;

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

            <FormInput>
              <MarkdownEditor
                {...field}
                {...props}
                className={classNames("w-full")}
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
