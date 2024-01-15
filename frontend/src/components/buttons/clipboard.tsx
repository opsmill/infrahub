import { ClipboardDocumentCheckIcon, ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../utils/alert";
import { Tooltip } from "../utils/tooltip";
import { BUTTON_TYPES, Button } from "./button";

type tClipboard = {
  value: any;
  className?: string;
  alert?: string;
  tooltip?: string;
};

export const Clipboard = (props: tClipboard) => {
  const { value, alert = "Content copied", tooltip = "Copy content", className } = props;

  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    setIsCopied(true);

    await navigator.clipboard.writeText(value);

    toast(<Alert message={alert} type={ALERT_TYPES.INFO} />);

    setTimeout(() => {
      setIsCopied(false);
    }, 3000);
  };

  return (
    <Tooltip message={tooltip}>
      <Button buttonType={BUTTON_TYPES.INVISIBLE} onClick={handleCopy} className={className}>
        {!isCopied && <ClipboardDocumentIcon className="h-4 w-4" />}

        {isCopied && <ClipboardDocumentCheckIcon className="h-4 w-4" />}
      </Button>
    </Tooltip>
  );
};
