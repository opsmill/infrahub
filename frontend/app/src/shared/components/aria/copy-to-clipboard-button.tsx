import { CopyCheckIcon, CopyIcon } from "lucide-react";
import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";
import { classNames } from "@/shared/utils/common";

interface CopyToClipboardProps extends Omit<AriaButtonProps, "children" | "onPress"> {
  data: string;
}

export function CopyToClipboardButton({ data, className, ...props }: CopyToClipboardProps) {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <Tooltip message={isCopied ? "Copied!" : "Copy"}>
      <AriaButton
        className={classNames(
          focusVisibleStyle,
          "rounded-lg border border-transparent p-1 text-sm hover:bg-black/10",
          className
        )}
        onPress={() => copyToClipboard(data)}
        {...props}
      >
        {isCopied ? <CopyCheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
      </AriaButton>
    </Tooltip>
  );
}
