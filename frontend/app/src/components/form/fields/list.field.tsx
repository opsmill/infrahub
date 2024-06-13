import { FormField, FormInput, FormLabel, FormMessage } from "@/components/ui/form";
import { FormFieldProps } from "@/components/form/type";
import List from "@/components/list";
import { QuestionMark } from "@/components/display/question-mark";

const ListField = ({ defaultValue, description, label, name, rules, ...props }: FormFieldProps) => {
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
            <List {...field} {...props} />
          </FormInput>
          <FormMessage />
        </div>
      )}
    />
  );
};

export default ListField;
