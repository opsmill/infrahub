import { MarkdownEditor } from "@/components/editor";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import { LabelFormField } from "@/components/form/fields/common";

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
      render={({ field }) => (
        <div className="flex flex-col">
          <LabelFormField
            label={label}
            unique={unique}
            required={!!rules?.required}
            description={description}
          />

          <FormInput>
            <MarkdownEditor
              {...field}
              {...props}
              defaultValue={defaultValue as string | undefined}
              onChange={(value: string) => field.onChange(value)}
              className="w-full"
            />
          </FormInput>
          <FormMessage />
        </div>
      )}
    />
  );
};

export default TextareaField;
