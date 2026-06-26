import { Icon } from "@iconify-icon/react";
import { Button, type ButtonProps } from "@infrahub/ui";
import type { ReactNode } from "react";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

interface CopyToClipboardProps extends Omit<ButtonProps, "children"> {
  text: string;
  children?: ReactNode;
}

export const CopyToClipboard = ({
  text,
  size = "xs",
  shape = "circle",
  variant = "ghost",
  children,
  ...props
}: CopyToClipboardProps) => {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <Button
      size={size}
      shape={shape}
      variant={variant}
      onPress={() => copyToClipboard(text)}
      {...props}
    >
      <Icon
        icon={
          isCopied ? "mdi:checkbox-multiple-marked-outline" : "mdi:checkbox-multiple-blank-outline"
        }
        className="text-base"
      />

      {children}
    </Button>
  );
};
