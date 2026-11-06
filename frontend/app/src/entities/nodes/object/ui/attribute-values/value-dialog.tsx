import { Button, Modal } from "@infrahub/ui";
import { CopyCheckIcon, CopyIcon } from "lucide-react";
import type React from "react";
import { Heading } from "react-aria-components";

import { CopiedAnnouncement } from "@/shared/components/a11y/copied-announcement";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

export interface ValueDialogProps {
  title: string;
  subtitle: string;
  copyLabel: string;
  copyData: () => string;
  onClose: () => void;
  children: React.ReactNode;
}

/** The dialog that shows a whole attribute value, opened from a table cell or the detail view. */
export function ValueDialog({
  title,
  subtitle,
  copyLabel,
  copyData,
  onClose,
  children,
}: ValueDialogProps) {
  const { isCopied, copyCount, copyToClipboard } = useCopyToClipboard();

  return (
    <Modal isOpen onOpenChange={(isOpen) => !isOpen && onClose()} className="w-160 max-w-full">
      <div className="flex min-h-0 flex-col gap-3 p-3">
        <Heading slot="title" className="truncate p-1 font-semibold">
          {title} <span className="font-normal text-foreground-muted">· {subtitle}</span>
        </Heading>
        {children}
      </div>

      <div className="flex justify-end gap-2 bg-content-muted p-3">
        <Button variant="outline" onPress={() => copyToClipboard(copyData())}>
          {isCopied ? <CopyCheckIcon /> : <CopyIcon />}
          {copyLabel}
        </Button>
        <Button onPress={onClose}>Close</Button>
      </div>
      <CopiedAnnouncement isCopied={isCopied} copyCount={copyCount} />
    </Modal>
  );
}
