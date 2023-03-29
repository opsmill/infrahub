import { Switch as HSwitch } from "@headlessui/react";

// type SwitchProps = {}

export const Switch = (props: any) => {
  const { enabled, onChange} = props;

  return (
    <HSwitch
      checked={enabled}
      onChange={onChange}
      className={`${
        enabled ? "bg-blue-500" : "bg-gray-200"
      } relative inline-flex h-6 w-11 items-center rounded-full`}
    >
      <span
        className={`${
          enabled ? "translate-x-6" : "translate-x-1"
        } inline-block h-4 w-4 transform rounded-full bg-white transition`}
      />
    </HSwitch>
  );
};
