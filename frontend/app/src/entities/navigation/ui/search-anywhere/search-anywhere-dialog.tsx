import { ModalOverlay } from "@infrahub/ui";
import type React from "react";
import { Dialog, Modal } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

import { useSearchAnywhereContext } from "@/entities/navigation/ui/search-anywhere/search-anywhere-context";

export function SearchAnywhereDialog({ children }: { children: React.ReactNode }) {
  const { isOpen, setIsOpen } = useSearchAnywhereContext();

  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={setIsOpen}>
      <Modal
        className={classNames(
          "fixed top-1 left-1/2 z-50 w-full max-w-(--breakpoint-md) -translate-x-1/2 rounded-2xl p-1",
          "border border-modal-frame-border bg-modal-frame shadow-modal backdrop-blur-lg",
          "data-entering:zoom-in-95 data-entering:slide-in-from-top-1/2 data-entering:animate-in data-entering:duration-200",
          "data-exiting:zoom-out-95 data-exiting:slide-out-to-top-1/2 data-exiting:animate-out data-exiting:duration-150"
        )}
      >
        <Dialog
          aria-label="Search anywhere"
          data-testid="search-anywhere"
          className="no-scrollbar max-h-[calc(var(--visual-viewport-height)*0.95)] overflow-auto rounded-xl bg-background p-2 outline-hidden"
        >
          {children}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
