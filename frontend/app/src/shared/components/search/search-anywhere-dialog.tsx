import { Dialog, DialogProps, Modal, ModalOverlay } from "react-aria-components";

import { useSearchAnywhereContext } from "@/shared/components/search/search-anywhere-context";
import { classNames } from "@/shared/utils/common";

export function SearchAnywhereDialog({ children, className, ...props }: DialogProps) {
  const { isOpen, setIsOpen } = useSearchAnywhereContext();

  return (
    <ModalOverlay
      isDismissable
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      className={classNames(
        "absolute overflow-auto inset-0 z-50 bg-gray-600/25",
        "data-entering:animate-in data-entering:fade-in-0",
        "data-exiting:duration-300 data-exiting:animate-out data-exiting:fade-out-0"
      )}
      {...props}
    >
      <Modal
        className={classNames(
          "fixed top-1 left-1/2 -translate-x-1/2 z-50 grid w-full max-w-(--breakpoint-md) gap-4 border border-gray-200 bg-stone-100 p-2 shadow-lg rounded-xl duration-200",
          "data-entering:animate-in data-entering:fade-in-0 data-entering:zoom-in-95 data-entering:slide-in-from-top-1/2",
          "data-exiting:duration-300 data-exiting:animate-out data-exiting:fade-out-0 data-exiting:zoom-out-95 data-exiting:slide-out-to-top-1/2",
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
