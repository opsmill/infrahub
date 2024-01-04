import { classNames } from "../../utils/common";

export enum TooltipPosition {
  TOP,
  LEFT,
  RIGHT,
  BOTTOM,
}

type TooltipProps = {
  children: any;
  message: any;
  position?: TooltipPosition;
};

const getPositionClassName: { [key in TooltipPosition]: string } = {
  [TooltipPosition.LEFT]: "top-1/2 right-8 transform -translate-y-1/2",
  [TooltipPosition.RIGHT]: "top-1/2 left-8 transform -translate-y-1/2",
  [TooltipPosition.TOP]: "bottom-8 left-1/2 transform -translate-x-1/2",
  [TooltipPosition.BOTTOM]: "top-8 left-1/2 transform -translate-x-1/2",
};

export const Tooltip = (props: TooltipProps) => {
  const { message, children, position } = props;

  return (
    <div className={"group/tooltip relative flex cursor-pointer"}>
      <span
        className={classNames(
          position ? getPositionClassName[position] : getPositionClassName[TooltipPosition.BOTTOM],
          `whitespace-pre absolute -z-10
          px-3 py-2 min-w-min
          text-sm font-medium text-white text-center
          bg-gray-600 rounded-lg shadow-sm opacity-0
          transition-opacity delay-500
          group-hover/tooltip:opacity-100
          group-hover/tooltip:z-10`
        )}>
        {message}
      </span>
      {children}
    </div>
  );
};
