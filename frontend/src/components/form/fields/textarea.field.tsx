import { MarkdownEditor } from "../../editor";
import { FormField, FormInput, FormLabel, FormMessage } from "../@/ui/form";
import { FormFieldProps } from "./common";

const TextareaField = ({ defaultValue, label, name, rules, ...props }: FormFieldProps) => {
  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => (
        <div className="flex flex-col items-start">
          <FormLabel className="mb-1">
            {label} {rules?.required && "*"}
          </FormLabel>

          <FormInput>
            <MarkdownEditor
              {...field}
              {...props}
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
