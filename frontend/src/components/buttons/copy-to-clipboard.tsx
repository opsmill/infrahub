import React, { useState } from "react";
import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";
import { Button, ButtonProps } from "./button-primitive";

interface CopyToClipboardProps extends ButtonProps {
  text: string;
}

export const CopyToClipboard = ({ text, ...props }: CopyToClipboardProps) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000); // Reset copied state after 2 seconds
    } catch (error) {
      console.error("Failed to copy: ", error);
    }
  };

  return (
    <Button size="icon" variant="ghost" onClick={handleCopy} {...props}>
      <Icon
        icon={
          copied ? "mdi:checkbox-multiple-marked-outline" : "mdi:checkbox-multiple-blank-outline"
        }
        className={classNames("text-base", copied && "text-green-700")}
      />
    </Button>
  );
};
