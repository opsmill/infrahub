import { Tooltip } from "@infrahub/ui";
import { ClipboardCheckIcon, ClipboardIcon } from "lucide-react";
import { Button } from "react-aria-components";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

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
    <Tooltip message={tooltip}>
      <Button onClick={handleCopy} className={className}>
        {!isCopied && <ClipboardIcon className="h-4 w-4" />}

        {isCopied && <ClipboardCheckIcon className="h-4 w-4" />}
      </Button>
    </Tooltip>
  );
};
