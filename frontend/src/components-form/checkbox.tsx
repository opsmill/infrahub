import { useState } from "react";
import { Checkbox } from "../components/checkbox";

interface Props {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: string;
}

export default function OpsSwitch(props: Props) {
  const { label, onChange, value, error } = props;
  const [enabled, setEnabled] = useState(value);

  return (
    <div className="flex flex-col">
      <label className="block text-sm font-medium leading-6 text-gray-900 capitalize">
        {label}
      </label>
      <Checkbox
        enabled={enabled}
        onChange={() => {
          onChange(!enabled);
          setEnabled(!enabled);
        }}
      />
      {error && <div>{error}</div>}
    </div>
  );
}
