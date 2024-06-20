import { FormLabel } from "@/components/ui/form";
import { QuestionMark } from "@/components/display/question-mark";
import { classNames } from "@/utils/common";
import { LabelProps } from "@headlessui/react/dist/components/label/label";

export const InputUniqueTips = () => (
  <span className="text-xs text-gray-600 italic self-end mb-px">must be unique</span>
);

interface LabelFormFieldProps extends LabelProps {
  className?: string;
  label?: string;
  required?: boolean;
  unique?: boolean;
  description?: string;
  variant?: string;
}

export const LabelFormField = ({
  className,
  label,
  required,
  unique,
  description,
  variant,
}: LabelFormFieldProps) => {
  return (
    <div className={classNames("mb-1 flex items-center gap-1", className)}>
      <FormLabel variant={variant}>
        {label} {required && "*"}
      </FormLabel>
      {unique && <InputUniqueTips />}
      {description && <QuestionMark message={description} />}
    </div>
  );
};
