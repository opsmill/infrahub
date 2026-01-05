import { Icon } from "@iconify-icon/react";
import {
  Radio as AriaRadio,
  RadioGroup as AriaRadioGroup,
  type RadioGroupProps as AriaRadioGroupProps,
  type RadioProps as AriaRadioProps,
  composeRenderProps,
} from "react-aria-components";

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
              "flex size-4 items-center justify-center rounded-full border border-gray-300",
              "transition-colors group-data-focus-visible/radio:border-custom-blue-600 group-data-focus-visible/radio:outline-hidden group-data-focus-visible/radio:ring-2 group-data-focus-visible/radio:ring-custom-blue-600/25",
              "group-data-invalid/radio:border-red-600"
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
