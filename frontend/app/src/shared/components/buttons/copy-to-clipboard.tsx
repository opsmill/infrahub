import { Icon } from "@iconify-icon/react";

import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";
import { classNames } from "@/shared/utils/common";

import { Button, type ButtonProps } from "../ui/button";

interface CopyToClipboardProps extends ButtonProps {
  text: string;
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
    <Button size={size} variant={variant} onClick={() => copyToClipboard(text)} {...props}>
      <Icon
        icon={
          isCopied ? "mdi:checkbox-multiple-marked-outline" : "mdi:checkbox-multiple-blank-outline"
        }
        className={classNames("text-base", children && "mr-2")}
      />

      {children}
    </Button>
  );
};
