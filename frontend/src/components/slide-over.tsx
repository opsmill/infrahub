import { Dialog, Transition } from "@headlessui/react";
import React, { Fragment } from "react";

interface Props {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  children: React.ReactNode;
  title: string | React.ReactNode;
  offset?: number;
}

export default function SlideOver(props: Props) {
  const { open, setOpen, title, offset = 0 } = props;

  // Need to define full classes so tailwind can compile the css
  const panelWidth = "w-[400px]";

  const offestWidth: { [key: number]: string } = {
    0: "-translate-x-0",
    1: "-translate-x-[400px]",
  };

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-10" onClose={setOpen}>
        <Transition.Child
          as={Fragment}
          enter="ease-in-out duration-500"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in-out duration-500"
          leaveFrom="opacity-100"
          leaveTo="opacity-0">
          <div
            className="fixed inset-0 bg-black bg-opacity-40 transition-opacity"
            data-cy="side-panel-background"
          />
        </Transition.Child>

        <div className="before:fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-in-out duration-500 sm:duration-700"
                enterFrom="translate-x-full"
                enterTo={`${offestWidth[offset]}`}
                leave="transform transition ease-in-out duration-500 sm:duration-700"
                leaveFrom={`${offestWidth[offset]}`}
                leaveTo="translate-x-full">
                <Dialog.Panel
                  className={`bg-custom-white pointer-events-auto ${panelWidth} shadow-xl flex flex-col`}>
                  <div className="px-4 py-4 sm:px-4 bg-gray-50 border-b">
                    <div className="w-full">
                      <Dialog.Title className="text-base leading-6">{title}</Dialog.Title>
                    </div>
                  </div>
                  {props.children}
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
