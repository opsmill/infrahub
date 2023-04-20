import { ChangeEvent } from "react";
import { classNames } from "../utils/common";
import { Input } from "../components/input";

interface Props {
  label: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  className?: string;
}

export const OpsInput = (props: Props) => {
  const { className, onChange, value, label } = props;

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900">
        {label}
      </label>
      <Input
        onChange={onChange}
        defaultValue={value ?? ""}
        className={classNames(className ?? "")}
      />
    </>
  );
};
