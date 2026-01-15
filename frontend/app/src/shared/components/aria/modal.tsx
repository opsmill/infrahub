import {
  Dialog as AriaDialog,
  Modal as AriaModal,
  ModalOverlay as AriaModalOverlay,
  type ModalOverlayProps as AriaModalOverlayProps,
  type DialogProps,
} from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export function ModalOverlay({ className, ...props }: AriaModalOverlayProps) {
  return (
    <AriaModalOverlay
      isDismissable
      className={classNames(
        "absolute inset-0 z-50 overflow-hidden bg-gray-600/25",
        "data-entering:fade-in-0 data-entering:animate-in data-entering:duration-200",
        "data-exiting:fade-out-0 data-exiting:animate-out data-exiting:duration-150",
        className
      )}
      {...props}
    />
  );
}

interface ModalProps
  extends Pick<AriaModalOverlayProps, "isOpen" | "onOpenChange" | "isDismissable">,
    DialogProps {}

export function Modal({ isOpen, onOpenChange, className, isDismissable, ...props }: ModalProps) {
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange} isDismissable={isDismissable}>
      <AriaModal
        className={classNames(
          "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
          "no-scrollbar box-border max-h-[calc(var(--visual-viewport-height)*.9)] max-w-[90vw] overflow-auto rounded-xl bg-white p-2",
          "data-entering:zoom-in-80 data-entering:animate-in data-entering:duration-200 data-entering:ease-out",
          "data-exiting:zoom-out-80 data-exiting:animate-out data-exiting:duration-150 data-exiting:ease-in",
          className
        )}
      >
        <AriaDialog className="outline-hidden" {...props} />
      </AriaModal>
    </ModalOverlay>
  );
}
