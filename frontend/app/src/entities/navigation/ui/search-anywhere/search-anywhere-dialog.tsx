import { Dialog, type DialogProps, Modal } from "react-aria-components";

import { ModalOverlay } from "@/shared/components/aria/modal";
import { classNames } from "@/shared/utils/common";

import { useSearchAnywhereContext } from "@/entities/navigation/ui/search-anywhere/search-anywhere-context";

export function SearchAnywhereDialog({ children, className, ...props }: DialogProps) {
  const { isOpen, setIsOpen } = useSearchAnywhereContext();

  return (
    <ModalOverlay isOpen={isOpen} onOpenChange={setIsOpen}>
      <Modal
        className={classNames(
          "fixed top-1 left-1/2 z-50 grid w-full max-w-(--breakpoint-md) -translate-x-1/2 gap-4 rounded-xl border border-gray-200 bg-stone-100 p-2 shadow-lg",
          "data-entering:zoom-in-95 data-entering:slide-in-from-top-1/2 data-entering:animate-in data-entering:duration-200",
          "data-exiting:zoom-out-95 data-exiting:slide-out-to-top-1/2 data-exiting:animate-out data-exiting:duration-150",
          className
        )}
        {...props}
      >
        <Dialog
          aria-label="Search anywhere"
          data-testid="search-anywhere"
          className="overflow-hidden"
        >
          {children}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
