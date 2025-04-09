import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";
import { Button as AriaButton, ButtonProps as AriaButtonProps } from "react-aria-components";

export function ToolbarButton({ className, ...props }: AriaButtonProps) {
  return (
    <AriaButton
      className={classNames(
        focusVisibleStyle,
        "border border-neutral-200 bg-white rounded-lg px-2 py-1 hover:bg-neutral-50",
        className
      )}
      {...props}
    />
  );
}
