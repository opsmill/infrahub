import { Icon } from "@iconify-icon/react";
import React, { useState } from "react";
import { Button, ButtonProps } from "./button-primitive";

interface CopyToClipboardProps extends ButtonProps {
  text: string;
}

export const CopyToClipboard = ({
  text,
  size = "icon",
  variant = "ghost",
  ...props
}: CopyToClipboardProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (event: React.MouseEvent<HTMLElement>) => {
    try {
      event.stopPropagation();

      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000); // Reset copied state after 2 seconds
    } catch (error) {
      console.error("Failed to copy: ", error);
    }
  };

  return (
    <Button size={size} variant={variant} onClick={handleCopy} {...props}>
      <Icon
        icon={
          copied ? "mdi:checkbox-multiple-marked-outline" : "mdi:checkbox-multiple-blank-outline"
        }
        className={"text-base"}
      />
    </Button>
  );
};
