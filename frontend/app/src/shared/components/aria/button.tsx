import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";

import { disabledStyle } from "@/shared/components/style-rac";
import {
  PushableItem,
  type PushableItemProps,
  pushableItemContainerStyle,
} from "@/shared/components/ui/pushable-item";
import { classNames } from "@/shared/utils/common";

export interface ButtonProps extends AriaButtonProps, Pick<PushableItemProps, "variant"> {
  containerClassName?: string;
}

export function Button({
  className,
  containerClassName,
  variant,
  children,
  ...props
}: ButtonProps) {
  return (
    <AriaButton
      className={classNames(disabledStyle, pushableItemContainerStyle, containerClassName)}
      {...props}
    >
      {(renderProps) => (
        <PushableItem
          variant={variant}
          isElevated={renderProps.isFocused || renderProps.isHovered || renderProps.isPressed}
          isPressed={renderProps.isPressed}
          isFocusVisible={renderProps.isFocusVisible}
          className={classNames(
            "inline-flex items-center justify-center gap-1.5",
            typeof className === "function"
              ? className({ ...renderProps, defaultClassName: undefined })
              : className
          )}
        >
          {typeof children === "function" ? children(renderProps) : children}
        </PushableItem>
      )}
    </AriaButton>
  );
}
