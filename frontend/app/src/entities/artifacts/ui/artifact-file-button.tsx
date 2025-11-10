import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";

export function ArtifactFileButton({ className, ...props }: AriaButtonProps) {
  return (
    <AriaButton
      className={classNames(
        focusVisibleStyle,
        "rounded-lg border border-transparent p-1 text-sm hover:bg-neutral-600",
        className
      )}
      {...props}
    />
  );
}
