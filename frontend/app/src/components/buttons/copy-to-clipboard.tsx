import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Button, ButtonProps } from "./button-primitive";

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
    <Button size={size} variant={variant} onClick={handleCopy} {...props}>
      <Icon
        icon={
          copied ? "mdi:checkbox-multiple-marked-outline" : "mdi:checkbox-multiple-blank-outline"
        }
        className={classNames("text-base", children && "mr-2")}
      />
      {children}
    </Button>
  );
};
