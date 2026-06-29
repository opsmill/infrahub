import { Icon } from "@iconify-icon/react";
import { Button, Modal } from "@infrahub/ui";
import type { ComponentProps, ReactNode } from "react";
import { Heading } from "react-aria-components";

import { Col, Row } from "@/shared/components/container";

interface ModalConfirmProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description?: ReactNode;
  onConfirm: () => void | Promise<void>;
  isLoading?: boolean;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: ComponentProps<typeof Button>["variant"];
  icon?: string;
  iconClassName?: string;
  iconContainerClassName?: string;
}

export function ModalConfirm({
  isOpen,
  onOpenChange,
  title,
  description,
  onConfirm,
  isLoading,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmVariant = "primary",
  icon = "mdi:alert-circle-outline",
  iconClassName = "text-yellow-600",
  iconContainerClassName = "bg-yellow-100",
}: ModalConfirmProps) {
  return (
    <Modal isDismissable={!isLoading} isOpen={isOpen} onOpenChange={onOpenChange}>
      <Col className="p-3">
        <Heading slot="title" className="flex items-center gap-2 p-1 font-semibold">
          <div
            className={`flex size-8 shrink-0 items-center justify-center rounded-full ${iconContainerClassName}`}
          >
            <Icon icon={icon} className={iconClassName} />
          </div>
          {title}
        </Heading>

        {description && <p className="px-8 text-gray-500 text-sm">{description}</p>}
      </Col>

      <Row className="justify-end bg-gray-50 p-3">
        <Button variant="outline" onPress={() => onOpenChange(false)} isDisabled={isLoading}>
          {cancelLabel}
        </Button>
        <Button
          variant={confirmVariant}
          onPress={onConfirm}
          isPending={isLoading}
          isDisabled={isLoading}
        >
          {confirmLabel}
        </Button>
      </Row>
    </Modal>
  );
}
