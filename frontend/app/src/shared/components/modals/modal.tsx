import { Dialog, Transition } from "@headlessui/react";
import React, { Fragment, ReactNode, useRef } from "react";

import { Button } from "@/shared/components/buttons/button";

export function ModalTitle({ children }: { children: ReactNode }) {
  return (
    <Dialog.Title as="h3" className="flex items-center font-semibold leading-6 text-gray-900">
      {children}
    </Dialog.Title>
  );
}

export function ModalDescription({ children }: { children: ReactNode }) {
  return <p className="text-sm text-gray-500">{children}</p>;
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
          <div className="flex min-h-full justify-center text-center items-center p-0">
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
                className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all my-8 w-full max-w-lg"
                data-cy="modal-delete"
                data-testid="modal-delete"
              >
                <div className="bg-white px-4 pt-5 p-6 pb-4">{children}</div>

                <div className="bg-gray-50 px-4 py-3 flex flex-row-reverse">
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
