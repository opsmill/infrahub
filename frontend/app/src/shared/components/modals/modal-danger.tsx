import { Button, Modal } from "@infrahub/ui";
import type { ReactNode } from "react";
import { Heading } from "react-aria-components";

import { Col, Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";

interface ModalDangerProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description?: ReactNode;
  onConfirm: () => void | Promise<void>;
  isLoading?: boolean;
  confirmLabel?: string;
  cancelLabel?: string;
}

export function ModalDanger({
  isOpen,
  onOpenChange,
  title,
  description,
  onConfirm,
  isLoading,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
}: ModalDangerProps) {
  return (
    <Modal
      isDismissable={!isLoading}
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      data-testid="modal-delete"
    >
      <Col className="p-3">
        <Heading slot="title" className="flex items-center gap-2 p-1 font-semibold">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-danger-surface">
            <Icon icon="mdi:warning-outline" className="text-danger" />
          </div>
          {title}
        </Heading>

        {description && <div className="px-8 text-foreground-muted text-sm">{description}</div>}
      </Col>

      <Row className="justify-end bg-gray-50 p-3 dark:bg-white/5">
        <Button variant="outline" onPress={() => onOpenChange(false)} isDisabled={isLoading}>
          {cancelLabel}
        </Button>
        <Button
          variant="danger"
          onPress={onConfirm}
          isPending={isLoading}
          isDisabled={isLoading}
          data-testid="modal-delete-confirm"
        >
          {confirmLabel}
        </Button>
      </Row>
    </Modal>
  );
}
