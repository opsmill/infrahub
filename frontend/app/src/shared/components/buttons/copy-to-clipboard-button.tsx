import { Button, Tooltip } from "@infrahub/ui";
import { CopyCheckIcon, CopyIcon } from "lucide-react";
import type { ButtonProps as AriaButtonProps } from "react-aria-components";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

interface CopyToClipboardProps extends Omit<AriaButtonProps, "children" | "onPress"> {
  data: string;
}

export function CopyToClipboardButton({ data, ...props }: CopyToClipboardProps) {
  const { isCopied, copyCount, copyToClipboard } = useCopyToClipboard();

  return (
    <>
      <Tooltip message={isCopied ? "Copied!" : "Copy"}>
        <Button
          variant="ghost"
          shape="square"
          size="xs"
          className="text-foreground-muted"
          onPress={() => copyToClipboard(data)}
          {...props}
        >
          {isCopied ? <CopyCheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
        </Button>
      </Tooltip>
      <span role="status" className="sr-only">
        {isCopied && <span key={copyCount}>Copied to clipboard</span>}
      </span>
    </>
  );
}
