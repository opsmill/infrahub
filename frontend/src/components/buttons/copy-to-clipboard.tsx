import React, { useState } from "react";
import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";

type CopyToClipboardProps = {
  text: string;
};

export const CopyToClipboard = ({ text }: CopyToClipboardProps) => {
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
    <button
      type="button"
      onClick={handleCopy}
      className="text-gray-600 flex p-1.5 hover:bg-gray-100 rounded-full">
      <Icon
        icon={
          copied ? "mdi:checkbox-multiple-marked-outline" : "mdi:checkbox-multiple-blank-outline"
        }
        className={classNames("text-base", copied && "text-green-700")}
      />
    </button>
  );
};
