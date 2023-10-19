import { ClipboardDocumentCheckIcon, ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "./alert";
import { BUTTON_TYPES, Button } from "./button";
import Transition from "./transition";

type tClipboard = {
  value: any;
  className?: string;
  message?: string;
};

export const Clipboard = (props: tClipboard) => {
  const { value, message = "Content copied", className } = props;

  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    setIsCopied(true);

    await navigator.clipboard.writeText(value);

    toast(<Alert message={message} type={ALERT_TYPES.INFO} />);

    setTimeout(() => {
      setIsCopied(false);
    }, 3000);
  };

  return (
    <Button buttonType={BUTTON_TYPES.INVISIBLE} onClick={handleCopy} className={className}>
      <Transition>
        {!isCopied && <ClipboardDocumentIcon className="h-4 w-4" />}

        {isCopied && <ClipboardDocumentCheckIcon className="h-4 w-4" />}
      </Transition>
    </Button>
  );
};
