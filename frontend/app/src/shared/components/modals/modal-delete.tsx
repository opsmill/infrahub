import { Icon } from "@iconify-icon/react";
import type { ReactNode } from "react";
import { Heading } from "react-aria-components";

import { Modal } from "@/shared/components/aria/modal";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";

interface ModalDeleteProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description?: ReactNode;
  onDelete: () => void | Promise<void>;
  isLoading?: boolean;
}

export function ModalDelete({
  isOpen,
  onOpenChange,
  title,
  description,
  onDelete,
  isLoading,
}: ModalDeleteProps) {
  return (
    <Modal
      isDismissable={!isLoading}
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      className="w-full max-w-lg p-0"
      data-testid="modal-delete"
    >
      <Col className="p-3">
        <Heading slot="title" className="flex items-center gap-2 p-1 font-semibold">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-red-100">
            <Icon icon="mdi:warning-outline" className="text-red-600" />
          </div>
          {title}
        </Heading>

        {description && <p className="px-8 text-gray-500 text-sm">{description}</p>}
      </Col>

      <Row className="justify-end bg-gray-50 p-3">
        <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          variant="danger"
          onClick={onDelete}
          isLoading={isLoading}
          disabled={isLoading}
          data-testid="modal-delete-confirm"
        >
          Delete
        </Button>
      </Row>
    </Modal>
  );
}
