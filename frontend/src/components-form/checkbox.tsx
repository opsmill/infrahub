import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { Checkbox } from "../components/checkbox";

interface Props {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: string;
  isProtected?: boolean;
}

export default function OpsSwitch(props: Props) {
  const { label, onChange, value, error, isProtected } = props;
  const [enabled, setEnabled] = useState(value);

  return (
    <div className="flex flex-col">
      <div className="flex items-center">
        <label className="block text-sm font-medium leading-6 text-gray-900"> {label} </label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
      </div>
      <Checkbox
        enabled={enabled}
        onChange={() => {
          onChange(!enabled);
          setEnabled(!enabled);
        }}
        disabled={isProtected}
      />
      {error && <div>{error}</div>}
    </div>
  );
}
