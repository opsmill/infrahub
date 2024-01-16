import { classNames } from "../../utils/common";

const DEFAULT_CIRCLE_CLASS = "h-1.5 w-1.5 mr-1 fill-gray-400";

type tCircleProps = {
  className?: string;
};

export const Circle = (props: tCircleProps) => {
  const { className = "" } = props;

  return (
    <svg
      className={classNames(DEFAULT_CIRCLE_CLASS, className)}
      viewBox="0 0 6 6"
      aria-hidden="true">
      <circle cx={3} cy={3} r={3} />
    </svg>
  );
};
