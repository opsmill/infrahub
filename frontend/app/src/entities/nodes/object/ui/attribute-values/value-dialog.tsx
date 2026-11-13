import { Button, Modal } from "@infrahub/ui";
import { CopyCheckIcon, CopyIcon } from "lucide-react";
import type React from "react";
import { Heading } from "react-aria-components";

import { CopiedAnnouncement } from "@/shared/components/a11y/copied-announcement";
import { Col, Row } from "@/shared/components/container";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

export interface ValueDialogProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  subtitle: string;
  copyLabel: string;
  copyData: () => string;
  children: React.ReactNode;
}

export function ValueDialog({
  isOpen,
  onOpenChange,
  title,
  subtitle,
  copyLabel,
  copyData,
  children,
}: ValueDialogProps) {
  const { isCopied, copyCount, copyToClipboard } = useCopyToClipboard();

  return (
    <Modal isOpen={isOpen} onOpenChange={onOpenChange} className="w-160 max-w-full">
      <Col className="min-h-0 gap-3 p-3">
        <Heading slot="title" className="truncate p-1 font-semibold">
          {title} <span className="font-normal text-foreground-muted">· {subtitle}</span>
        </Heading>
        {children}
      </Col>

      <Row className="justify-end bg-content-muted p-3">
        <Button variant="outline" onPress={() => copyToClipboard(copyData())}>
          {isCopied ? <CopyCheckIcon /> : <CopyIcon />}
          {copyLabel}
        </Button>
        <Button onPress={() => onOpenChange(false)}>Close</Button>
      </Row>
      <CopiedAnnouncement isCopied={isCopied} copyCount={copyCount} />
    </Modal>
  );
}
