import { Switch as HSwitch } from "@headlessui/react";
import { classNames } from "../../utils/common";

// type SwitchProps = {}

export const Switch = (props: any) => {
  const { checked, onChange, error, disabled } = props;

  return (
    <div
      className={classNames(
        "relative px-1.5 py-2 rounded-md",
        error ? "border-2 border-red-300 pb-3" : ""
      )}>
      <HSwitch
        disabled={disabled}
        checked={checked}
        onChange={onChange}
        className={`${
          checked ? "bg-custom-blue-500" : "bg-gray-200"
        } relative inline-flex h-6 w-11 items-center rounded-full`}>
        <span
          className={`${
            checked ? "translate-x-6" : "translate-x-1"
          } inline-block h-4 w-4 transform rounded-full bg-custom-white transition`}
        />
      </HSwitch>
      {error && error?.message && (
        <div className="absolute text-sm text-red-500 bg-custom-white -bottom-2 ml-2 px-2">
          {error?.message}
        </div>
      )}
    </div>
  );
};
