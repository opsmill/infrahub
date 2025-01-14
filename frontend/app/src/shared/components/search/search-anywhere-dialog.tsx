import { useSearchAnywhereContext } from "@/shared/components/search/search-anywhere-context";
import { classNames } from "@/shared/utils/common";
import { Command } from "cmdk";
import React from "react";

export function SearchAnywhereDialog({
  children,
  ...props
}: React.ComponentProps<typeof Command.Dialog>) {
  const { isOpen, setIsOpen } = useSearchAnywhereContext();

  return (
    <Command.Dialog
      {...props}
      open={isOpen}
      onOpenChange={setIsOpen}
      overlayClassName={classNames(
        "fixed inset-0 z-50 bg-gray-600/25",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0"
      )}
      contentClassName={classNames(
        "fixed top-1 left-[50%] translate-x-[-50%] z-50 grid w-full max-w-screen-md gap-4 border bg-stone-100 p-2 shadow-lg rounded-xl duration-200",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%]"
      )}
      data-testid="search-anywhere"
      className="overflow-hidden"
      shouldFilter={false}
      label="Search anywhere"
    >
      {children}
    </Command.Dialog>
  );
}
