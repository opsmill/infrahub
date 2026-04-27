import { Icon } from "@iconify-icon/react";
import type { ReactNode } from "react";

import { Button, type ButtonProps } from "@/shared/components/aria/button";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

interface CopyToClipboardProps extends Omit<ButtonProps, "children"> {
  text: string;
  children?: ReactNode;
}

export const CopyToClipboard = ({
  text,
  size = "icon",
  variant = "ghost",
  children,
  ...props
}: CopyToClipboardProps) => {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <Button size={size} variant={variant} onPress={() => copyToClipboard(text)} {...props}>
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
