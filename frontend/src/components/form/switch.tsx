import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { QuestionMark } from "../display/question-mark";
import { Switch } from "../inputs/switch";

interface Props {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  field: any;
}

export default function OpsSwitch(props: Props) {
  const { label, onChange, value, error, isProtected, isOptional, field } = props;
  const [enabled, setEnabled] = useState(value);

  return (
    <div className="flex flex-col items-center">
      <div className="flex items-center">
        <label className="block text-sm font-medium leading-6 text-gray-900">
          {label} {isOptional ? "" : "*"}
        </label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
        <QuestionMark message={field.description} />
      </div>
      <Switch
        error={error}
        checked={enabled}
        onChange={() => {
          setEnabled(!enabled);
          onChange(!enabled);
        }}
        disabled={isProtected}
      />
    </div>
  );
}
