import { Dialog, Transition } from "@headlessui/react";
import type React from "react";
import { Fragment, type ReactNode, useRef } from "react";

import { Button } from "@/shared/components/buttons/button";

export function ModalTitle({ children }: { children: ReactNode }) {
  return (
    <Dialog.Title as="h3" className="flex items-center font-semibold text-gray-900 leading-6">
      {children}
    </Dialog.Title>
  );
}

interface iProps {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  children?: ReactNode;
  closeLabel?: string;
}

export default function Modal({ open, setOpen, children, closeLabel }: iProps) {
  const closeButtonRef = useRef(null);

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-10" initialFocus={closeButtonRef} onClose={setOpen}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-0 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 translate-y-0 scale-95"
              enterTo="opacity-100 translate-y-0 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 scale-100"
              leaveTo="opacity-0 translate-y-4 translate-y-0 scale-95"
            >
              <Dialog.Panel
                className="relative my-8 w-full max-w-lg transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all"
                data-cy="modal-delete"
                data-testid="modal-delete"
              >
                <div className="bg-white p-6 px-4 pt-5 pb-4">{children}</div>

                <div className="flex flex-row-reverse bg-gray-50 px-4 py-3">
                  <Button onClick={() => setOpen(false)} ref={closeButtonRef}>
                    {closeLabel ?? "Close"}
                  </Button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
