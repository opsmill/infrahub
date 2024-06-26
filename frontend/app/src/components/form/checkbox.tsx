import { QuestionMark } from "@/components/display/question-mark";
import { Checkbox } from "@/components/inputs/checkbox";
import { components } from "@/infraops";
import { FormFieldError } from "@/screens/edit-form-hook/form";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useState } from "react";

interface Props {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  field:
    | components["schemas"]["AttributeSchema-Output"]
    | components["schemas"]["RelationshipSchema-Output"];
}

export default function OpsCheckbox(props: Props) {
  const { label, onChange, value, error, isProtected, isOptional, field } = props;
  const [enabled, setEnabled] = useState(value);

  return (
    <div className="flex flex-col relative">
      <div className="flex items-center">
        <label htmlFor={label} className="block text-sm font-medium leading-6 text-gray-900">
          {label} {isOptional ? "" : "*"}
        </label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
        <QuestionMark message={field?.description} />
      </div>
      <div className="relative flex items-center">
        <Checkbox
          id={label}
          enabled={enabled}
          onChange={() => {
            onChange(!enabled);
            setEnabled(!enabled);
          }}
          disabled={isProtected}
        />
        {error?.message && (
          <div className="absolute text-sm text-red-500 ml-4 pl-2" data-cy="field-error-message">
            {error?.message}
          </div>
        )}
      </div>
    </div>
  );
}
