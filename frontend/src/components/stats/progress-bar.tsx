import { classNames } from "../../utils/common";

type tProgressBar = {
  value: number;
  displayValue?: boolean;
};

const getCleanedValue = (value: number) => {
  if (isNaN(value)) return 0;

  if (value > 100) return 100;

  return value;
};

export default function ProgressBar(props: tProgressBar) {
  const { value, displayValue } = props;

  const cleanedValue = getCleanedValue(value);

  return (
    <div className={classNames("w-full bg-gray-300 rounded-full", displayValue ? "h-4" : "h-2")}>
      <div
        style={{ width: `${cleanedValue}%` }}
        className={"h-full bg-custom-blue-500 rounded-full flex items-center justify-center"}>
        {displayValue && <span className="text-xs text-custom-white">{cleanedValue}%</span>}
      </div>
    </div>
  );
}
