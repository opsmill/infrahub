import {
  Dialog as AriaDialog,
  Modal as AriaModal,
  ModalOverlay as AriaModalOverlay,
  type ModalOverlayProps as AriaModalOverlayProps,
  type DialogProps,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { Stacked } from "../../utils/stacked";

const CENTER_PERCENT = 50;
const TOP_OFFSET_PER_LAYER = 4;
const BASE_SCALE = 1;
const SCALE_DECREASE_PER_LAYER = 0.05;

export interface ModalOverlayProps extends AriaModalOverlayProps {}

export function ModalOverlay({ className, ...props }: ModalOverlayProps) {
  return (
    <AriaModalOverlay
      isDismissable
      className={cn(
        "absolute inset-0 z-50 overflow-hidden bg-black/25",
        "data-entering:fade-in-0 data-entering:animate-in data-entering:duration-200",
        "data-exiting:fade-out-0 data-exiting:animate-out data-exiting:duration-150",
        className
      )}
      {...props}
    />
  );
}

export interface ModalProps
  extends Omit<AriaModalOverlayProps, "children">,
    Pick<DialogProps, "aria-label" | "children"> {}

export function Modal({
  "aria-label": ariaLabel,
  children,
  isOpen,
  onOpenChange,
  className,
  isDismissable = true,
  ...props
}: ModalProps) {
  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange} isDismissable={isDismissable}>
      {({ state: { isOpen: isOpenOverlay } }) => (
        <Stacked group="modal" isStacked={isOpenOverlay}>
          {({ depth }) => (
            <AriaModal
              className={cn(
                "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 transition-all duration-200",
                "no-scrollbar box-border flex max-h-[calc(var(--visual-viewport-height)*0.99)] max-w-[90vw] flex-col overflow-hidden rounded-2xl p-1",
                "border border-modal-frame-border bg-modal-frame shadow-modal backdrop-blur-lg",
                "data-entering:zoom-in-80 data-entering:animate-in data-entering:duration-200 data-entering:ease-out",
                "data-exiting:zoom-out-80 data-exiting:animate-out data-exiting:duration-150 data-exiting:ease-in"
              )}
              style={{
                top: `${CENTER_PERCENT - depth * TOP_OFFSET_PER_LAYER}%`,
                scale: BASE_SCALE - depth * SCALE_DECREASE_PER_LAYER,
              }}
              {...props}
            >
              <AriaDialog
                aria-label={ariaLabel}
                className={cn(
                  "flex h-full min-h-0 w-full min-w-0 flex-col overflow-auto rounded-xl bg-secondary outline-hidden",
                  className
                )}
              >
                {children}
              </AriaDialog>
            </AriaModal>
          )}
        </Stacked>
      )}
    </ModalOverlay>
  );
}
