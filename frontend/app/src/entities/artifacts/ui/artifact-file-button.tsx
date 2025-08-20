import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";
import { Button as AriaButton, ButtonProps as AriaButtonProps } from "react-aria-components";

export function ArtifactFileButton({ className, ...props }: AriaButtonProps) {
  return (
    <AriaButton
      className={classNames(
        focusVisibleStyle,
        "border border-transparent p-1 hover:bg-neutral-600 rounded-lg text-sm",
        className
      )}
      {...props}
    />
  );
}
