import { BUTTON_TYPES, Button } from "@/components/buttons/button";
import { Dialog, Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import React, { Fragment, ReactNode, useRef } from "react";

interface iProps {
  open: boolean;
  hideCancel?: boolean;
  isLoading?: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  title: string;
  description?: string | React.ReactNode;
  onConfirm: Function;
  onCancel: Function;
  children?: ReactNode;
  icon?: string;
}

export default function ModalConfirm({
  title,
  description,
  onCancel,
  onConfirm,
  open,
  setOpen,
  isLoading,
  children,
  hideCancel,
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
          <div className="fixed inset-0 bg-black bg-opacity-40 transition-opacity" />
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
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-custom-white text-left shadow-xl transition-all my-8 w-full max-w-lg">
                <div className="bg-custom-white px-4 pt-5 p-6 pb-4">
                  <div className="">
                    <div className="ml-4 mt-0 text-left">
                      <Dialog.Title
                        as="h3"
                        className="flex items-center font-semibold leading-6 text-gray-900"
                      >
                        <div className="bg-red-100 rounded-full w-8 h-8 flex items-center justify-center mr-2">
                          <Icon icon={icon} className="text-red-600" aria-hidden="true" />
                        </div>
                        {title}
                      </Dialog.Title>
                      <div className="mt-2">
                        <p className="text-sm text-gray-500">{description}</p>
                        {children}
                      </div>
                    </div>
                  </div>
                </div>
                <div
                  className="bg-gray-50 px-4 py-3 flex flex-row-reverse"
                  data-cy="modal-confirm-buttons"
                >
                  <Button
                    onClick={onConfirm}
                    buttonType={BUTTON_TYPES.VALIDATE}
                    className="ml-2"
                    isLoading={isLoading}
                  >
                    Confirm
                  </Button>
                  {!hideCancel && (
                    <Button onClick={onCancel} ref={cancelButtonRef}>
                      Cancel
                    </Button>
                  )}
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
