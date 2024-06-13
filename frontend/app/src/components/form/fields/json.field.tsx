import { FormFieldProps } from "@/components/form/type";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { JsonEditor } from "@/components/editor/json/json-editor";
import { LabelFormField } from "@/components/form/fields/common";

const JsonField = ({
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
      render={({ field }) => (
        <div className="flex flex-col">
          <LabelFormField
            label={label}
            unique={unique}
            required={!!rules?.required}
            description={description}
          />

          <FormInput>
            <JsonEditor
              {...field}
              {...props}
              onChange={(value) => {
                if (!value) {
                  field.onChange(undefined);
                }

                try {
                  // Store the value as JSON
                  const newValue = JSON.parse(value);
                  field.onChange(newValue);
                } catch (e) {
                  field.onChange(value);
                }
              }}
              ref={(ref) => {
                // @ts-expect-error
                field.ref(ref?._input); // patch lib to be able to focus on form validation fails
              }}
            />
          </FormInput>
          <FormMessage />
        </div>
      )}
    />
  );
};

export default JsonField;
