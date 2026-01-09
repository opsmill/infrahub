import { Clipboard as ClipboardIcon, ClipboardCheck } from "lucide-react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

import { BUTTON_TYPES, Button } from "./button";

type tClipboard = {
  value: any;
  className?: string;
  alert?: string;
  tooltip?: string;
};

export const Clipboard = (props: tClipboard) => {
  const { value, alert = "Content copied", tooltip = "Copy content", className } = props;

  const { isCopied, copyToClipboard } = useCopyToClipboard();

  const handleCopy = async () => {
    await copyToClipboard(value);
    toast(<Alert message={alert} type={ALERT_TYPES.INFO} />);
  };

  return (
    <Tooltip enabled content={tooltip}>
      <Button buttonType={BUTTON_TYPES.INVISIBLE} onClick={handleCopy} className={className}>
        {!isCopied && <ClipboardIcon className="h-4 w-4" />}

        {isCopied && <ClipboardCheck className="h-4 w-4" />}
      </Button>
    </Tooltip>
  );
};
