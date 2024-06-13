import { MarkdownEditor } from "@/components/editor";
import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import { QuestionMark } from "@/components/display/question-mark";

const TextareaField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
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
          <div className="px-1 mb-1 flex justify-between items-center gap-1">
            <FormLabel>
              {label} {rules?.required && "*"}
            </FormLabel>

            {description && <QuestionMark message={description} />}
          </div>

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
