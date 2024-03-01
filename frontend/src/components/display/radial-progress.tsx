import { classNames } from "../../utils/common";

type tRadialProgress = {
  percent?: number;
  children?: any;
  bgColor?: string;
  color?: string;
};

export const RadialProgress = (props: tRadialProgress) => {
  const { percent = 0, children, bgColor, color } = props;

  const offset = 400 - (400 * (62 * percent)) / 100;

  return (
    <div className="relative w-16 h-1w-16">
      <svg className="w-full h-full" viewBox="0 0 100 100">
        <circle
          className={classNames("stroke-current", bgColor ?? "text-gray-200 ")}
          strokeWidth="10"
          cx="50"
          cy="50"
          r="40"
          fill="transparent"></circle>

        <circle
          className={classNames(
            "progress-ring__circle stroke-current",
            color ?? "text-custom-blue-500"
          )}
          strokeWidth="10"
          strokeLinecap="round"
          cx="50"
          cy="50"
          r="40"
          fill="transparent"
          strokeDashoffset={offset}></circle>
      </svg>

      <div className="absolute w-full h-full top-0 left-0 flex items-center justify-center">
        {children}
      </div>
    </div>
  );
};
