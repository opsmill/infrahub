import { ChangeEvent } from "react";
import { classNames } from "../utils/common";

interface Props {
  label: string;
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  className?: string;
}

const DEFAULT_CLASSNAME = `block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400
border-gray-300 bg-white
sm:text-sm sm:leading-6 px-3
focus:ring-2 focus:ring-inset focus:ring-indigo-600 focus:border-indigo-600 focus:outline-none
disabled:cursor-not-allowed disabled:bg-gray-100
`;

export const OpsInput = (props: Props) => {
  const { className, onChange, value, label } = props;

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900 mt-6">
        {label}
      </label>
      <input
        placeholder="YOLO"
        onChange={onChange}
        defaultValue={value ?? ""}
        className={classNames(DEFAULT_CLASSNAME, className ?? "")}
      />
    </>
  );
};
