import { FormLabel } from "@/components/ui/form";
import { QuestionMark } from "@/components/display/question-mark";

export const InputUniqueTips = () => (
  <span className="text-xs text-gray-600 italic self-end mb-px">must be unique</span>
);

type LabelFormFieldProps = {
  label?: string;
  required?: boolean;
  unique?: boolean;
  description?: string;
};

export const LabelFormField = ({ label, required, unique, description }: LabelFormFieldProps) => {
  return (
    <div className="px-1 mb-1 flex gap-1">
      <FormLabel>
        {label} {required && "*"}
      </FormLabel>
      {unique && <InputUniqueTips />}
      {description && <QuestionMark message={description} className="ml-auto" />}
    </div>
  );
};
