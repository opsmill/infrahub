import { Dialog, type DialogProps, Modal, ModalOverlay } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

import { useSearchAnywhereContext } from "@/entities/navigation/ui/search-anywhere/search-anywhere-context";

export function SearchAnywhereDialog({ children, className, ...props }: DialogProps) {
  const { isOpen, setIsOpen } = useSearchAnywhereContext();

  return (
    <ModalOverlay
      isDismissable
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      className={classNames(
        "absolute inset-0 z-50 overflow-auto bg-gray-600/25",
        "data-entering:fade-in-0 data-entering:animate-in",
        "data-exiting:fade-out-0 data-exiting:animate-out data-exiting:duration-300"
      )}
      {...props}
    >
      <Modal
        className={classNames(
          "-translate-x-1/2 fixed top-1 left-1/2 z-50 grid w-full max-w-(--breakpoint-md) gap-4 rounded-xl border border-gray-200 bg-stone-100 p-2 shadow-lg duration-200 dark:border-gray-700 dark:bg-gray-800",
          "data-entering:fade-in-0 data-entering:zoom-in-95 data-entering:slide-in-from-top-1/2 data-entering:animate-in",
          "data-exiting:fade-out-0 data-exiting:zoom-out-95 data-exiting:slide-out-to-top-1/2 data-exiting:animate-out data-exiting:duration-300",
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
