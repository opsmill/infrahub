import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { Switch } from "../components/inputs/switch";
import { FormFieldError } from "../screens/edit-form-hook/form";

interface Props {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
}

export default function OpsSwitch(props: Props) {
  const { label, onChange, value, error, isProtected, isOptional } = props;
  const [enabled, setEnabled] = useState(value);

  return (
    <div className="flex flex-col items-center">
      <div className="flex items-center">
        <label className="block text-sm font-medium leading-6 text-gray-900">
          {label} {isOptional ? "" : "*"}
        </label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
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
