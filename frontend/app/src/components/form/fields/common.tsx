import { FormLabel } from "@/components/ui/form";
import { QuestionMark } from "@/components/display/question-mark";
import { classNames } from "@/utils/common";

export const InputUniqueTips = () => (
  <span className="text-xs text-gray-600 italic self-end mb-px">must be unique</span>
);

type LabelFormFieldProps = {
  className?: string;
  label?: string;
  required?: boolean;
  unique?: boolean;
  description?: string;
};

export const LabelFormField = ({
  className,
  label,
  required,
  unique,
  description,
}: LabelFormFieldProps) => {
  return (
    <div className={classNames("px-1 mb-1 flex items-center gap-1", className)}>
      <FormLabel>
        {label} {required && "*"}
      </FormLabel>
      {unique && <InputUniqueTips />}
      {description && <QuestionMark message={description} />}
    </div>
  );
};
