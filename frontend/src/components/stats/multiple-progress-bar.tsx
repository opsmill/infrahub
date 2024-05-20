import * as ProgressPrimitive from "@radix-ui/react-progress";
import { classNames } from "../../utils/common";
import { Tooltip, TooltipProps } from "../ui/tooltip";

interface ProgressBarItemProps extends ProgressPrimitive.ProgressIndicatorProps {
  value: number;
  color?: string;
  tooltip?: TooltipProps["content"];
}

interface MultipleProgressBarProps extends ProgressPrimitive.ProgressProps {
  elements: Array<ProgressBarItemProps>;
}

const MultipleProgressBar = ({ elements, className, ...props }: MultipleProgressBarProps) => {
  const { length } = elements;
  const elementOrderedByValue = elements.sort((a, b) => a.value - b.value);

  return (
    <ProgressPrimitive.Root
      className={classNames(
        "h-2 w-full overflow-hidden rounded-full bg-custom-blue-600/10 flex",
        className
      )}
      {...props}>
      {elementOrderedByValue.map(
        ({ className, color, style, tooltip, value, ...props }, index, array) => {
          const previousValue = array[index - 1]?.value ?? 0;

          return (
            <Tooltip key={index} content={tooltip} enabled={!!tooltip} className="max-w-48">
              <ProgressPrimitive.Indicator
                className={classNames("h-full transition-all", className)}
                style={{
                  width: `${value - previousValue}%`,
                  backgroundColor: color ?? `rgba(9,135,168, ${1 - index * (1 / length)})`,
                  ...style,
                }}
                {...props}
              />
            </Tooltip>
          );
        }
      )}
    </ProgressPrimitive.Root>
  );
};

export default MultipleProgressBar;
