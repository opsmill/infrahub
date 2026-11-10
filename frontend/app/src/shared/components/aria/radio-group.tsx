import {
  Radio as AriaRadio,
  RadioGroup as AriaRadioGroup,
  type RadioGroupProps as AriaRadioGroupProps,
  type RadioProps as AriaRadioProps,
  composeRenderProps,
} from "react-aria-components";

import { Icon } from "@/shared/components/display/icon";
import { classNames } from "@/shared/utils/common";

export const RadioGroup = ({ className, ...props }: AriaRadioGroupProps) => {
  return (
    <AriaRadioGroup
      className={composeRenderProps(className, (className, renderProps) =>
        classNames(
          "relative flex flex-col flex-wrap gap-1",
          renderProps.orientation === "horizontal" && "flex-row items-center",
          className
        )
      )}
      {...props}
    />
  );
};

export const Radio = ({ className, children, ...props }: AriaRadioProps) => {
  return (
    <AriaRadio
      className={composeRenderProps(className, (className) =>
        classNames(
          "group/radio flex cursor-pointer items-center gap-x-2",
          "data-disabled:cursor-not-allowed data-disabled:opacity-70",
          className
        )
      )}
      {...props}
    >
      {composeRenderProps(children, (children, renderProps) => (
        <>
          <span
            className={classNames(
              "flex size-4 items-center justify-center rounded-full border border-border-strong",
              "transition-colors group-data-focus-visible/radio:border-ring group-data-focus-visible/radio:outline-hidden group-data-focus-visible/radio:ring-2 group-data-focus-visible/radio:ring-ring-halo",
              "group-data-invalid/radio:border-danger"
            )}
          >
            {renderProps.isSelected && (
              <Icon icon="mdi:circle" className="text-custom-blue-800 text-xs" />
            )}
          </span>
          {children}
        </>
      ))}
    </AriaRadio>
  );
};
