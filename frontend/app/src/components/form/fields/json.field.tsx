import { FormFieldProps } from "@/components/form/type";
import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { JsonEditor } from "@/components/editor/json/json-editor";
import { QuestionMark } from "@/components/display/question-mark";

const JsonField = ({ defaultValue, description, label, name, rules, ...props }: FormFieldProps) => {
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
