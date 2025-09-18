import { Dialog, Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Fragment, type ReactNode, useRef } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";

interface iProps {
  open: boolean;
  isLoading?: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  title: string;
  description?: string | React.ReactNode;
  onConfirm: () => void;
  children: ReactNode;
  icon?: string;
}

export default function ModalSuccess({
  title,
  description,
  onConfirm,
  open,
  setOpen,
  isLoading,
  children,
  icon = "mdi:warning-outline",
}: iProps) {
  const cancelButtonRef = useRef(null);

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-10" initialFocus={cancelButtonRef} onClose={setOpen}>
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
              <Dialog.Panel className="relative my-8 w-full max-w-lg transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all">
                <div className="bg-white p-6 px-4 pt-5 pb-4">
                  <div className="">
                    <div className="mt-0 ml-4 text-left">
                      <Dialog.Title
                        as="h3"
                        className="flex items-center font-semibold text-gray-900 leading-6"
                      >
                        <div className="mr-2 flex h-8 w-8 items-center justify-center rounded-full bg-custom-blue-1">
                          <Icon icon={icon} className="text-custom-blue-700" aria-hidden="true" />
                        </div>
                        {title}
                      </Dialog.Title>
                      <div className="mt-2">
                        <p className="text-gray-500 text-sm">{description}</p>
                        {children}
                      </div>
                    </div>
                  </div>
                </div>
                <div
                  className="flex flex-row-reverse bg-gray-50 px-4 py-3"
                  data-cy="modal-confirm-buttons"
                >
                  <Button
                    onClick={onConfirm}
                    variant="active"
                    className="ml-2"
                    isLoading={isLoading}
                  >
                    Confirm
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
