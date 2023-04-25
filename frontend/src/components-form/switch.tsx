import { useState } from "react";
import { Switch } from "../components/switch";

interface Props {
    label: string;
    value: boolean;
    onChange: (value: boolean) => void;
}

export default function OpsSwitch(props: Props) {
  const { label, onChange, value} = props;
  const [enabled, setEnabled] = useState(value);

  return (
    <div className="flex flex-col items-center">
      <label
        className="block text-sm font-medium leading-6 text-gray-900 capitalize">
        {label}
      </label>
      <Switch
        checked={enabled}
        onChange={
          () => {
            setEnabled(!enabled);
            onChange(!enabled);
          }
        }
      />
    </div>
  );
}