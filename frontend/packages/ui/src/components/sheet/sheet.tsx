import {
  Dialog as AriaDialog,
  type DialogProps as AriaDialogProps,
  Modal as AriaModal,
  type ModalOverlayProps as AriaModalOverlayProps,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { ModalOverlay } from "../../components/modal/modal";
import { DismissGuardContext, useDismissGuard } from "../../hooks/use-dissmiss-guard";
import { Stacked } from "../../utils/stacked";

const BASE_OFFSET = 8;
const OFFSET_PER_DEPTH = 40;
const SCALE_PER_DEPTH = 0.02;

export interface SheetProps
  extends Pick<AriaDialogProps, "aria-label" | "children" | "className">,
    Omit<AriaModalOverlayProps, "children" | "className"> {}

export function Sheet({
  isOpen,
  children,
  className,
  "aria-label": ariaLabel,
  onOpenChange,
  style,
  ...props
}: SheetProps) {
  const { setDismissable, guardedOnOpenChange } = useDismissGuard(onOpenChange);

  return (
    <DismissGuardContext value={{ setDismissable }}>
      <ModalOverlay isOpen={isOpen} onOpenChange={guardedOnOpenChange}>
        {({ state: { isOpen: isOpenOverlay } }) => (
          <Stacked group="sheet" isStacked={isOpenOverlay}>
            {({ depth, totalCount }) => (
              <AriaModal
                className={cn(
                  "fixed top-2 bottom-2 w-100 overflow-hidden rounded-2xl p-1 outline-hidden transition-all",
                  "border border-modal-frame-border bg-modal-frame shadow-modal backdrop-blur-lg",
                  "data-entering:slide-in-from-right-1/2 data-entering:animate-in data-entering:duration-200 data-entering:ease-out",
                  "data-exiting:slide-out-to-right-1/2 data-exiting:animate-out data-exiting:duration-150 data-exiting:ease-in"
                )}
                style={{
                  ...style,
                  right: `${BASE_OFFSET + depth * OFFSET_PER_DEPTH}px`,
                  scale: 1 - depth * SCALE_PER_DEPTH,
                }}
                {...props}
              >
                <AriaDialog
                  aria-label={ariaLabel ?? `sheet ${totalCount - depth}`}
                  className={cn(
                    "no-scrollbar h-full overflow-auto rounded-xl bg-secondary p-3 outline-hidden",
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
    </DismissGuardContext>
  );
}
