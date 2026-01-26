import { Dialog, Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import React, { Fragment, useRef, useState } from "react";

import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import { Badge } from "@/shared/components/ui/badge";
import usePrevious from "@/shared/hooks/usePrevious";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import type { ModelSchema } from "@/entities/schema/types";

interface Props {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  onClose?: () => void;
  children: React.ReactNode;
  title: string | React.ReactNode;
  offset?: number;
}

interface SlideOverContextProps {
  setPreventClose?: (value: boolean) => void;
}

export const SlideOverContext = React.createContext<SlideOverContextProps>({});

export default function SlideOver({ open, setOpen, onClose, title, offset = 0, children }: Props) {
  const initialFocusRef = useRef(null);
  const [preventClose, setPreventClose] = useState(false);
  const previousOpen = usePrevious(open);

  // Need to define full classes so tailwind can compile the css
  const panelWidth = "w-[400px]";

  const offestWidth: { [key: number]: string } = {
    0: "-translate-x-0",
    1: "-translate-x-[400px]",
  };

  const isOpen = open || (!open && !!previousOpen && preventClose);

  const context = {
    isOpen,
    setPreventClose: (value: boolean) => setPreventClose(value),
  };

  return (
    <SlideOverContext value={context}>
      <Transition.Root show={isOpen} as={Fragment}>
        <Dialog
          as="div"
          className="relative z-10"
          onClose={(value) => {
            setOpen(value);
            if (onClose) onClose();
          }}
          initialFocus={initialFocusRef}
        >
          <Transition.Child
            as={Fragment}
            enter="ease-in-out duration-500"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in-out duration-500"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div
              className="fixed inset-0 bg-black/40 transition-opacity"
              data-cy="side-panel-background"
              data-testid="side-panel-background"
            />
          </Transition.Child>

          <div className="inset-0 overflow-hidden before:fixed">
            <div className="absolute inset-0 overflow-hidden">
              <div className="pointer-events-none fixed inset-y-0 right-0 flex">
                <button type="button" tabIndex={-1} ref={initialFocusRef} />
                <Transition.Child
                  as={Fragment}
                  enter="transform transition ease-in-out duration-500"
                  enterFrom="translate-x-full"
                  enterTo={`${offestWidth[offset]}`}
                  leave="transform transition ease-in-out duration-500"
                  leaveFrom={`${offestWidth[offset]}`}
                  leaveTo="translate-x-full"
                >
                  <Dialog.Panel
                    className={`pointer-events-auto flex flex-col bg-white shadow-xl ${panelWidth} ${offestWidth[offset]}`}
                    data-testid="side-panel-container"
                  >
                    <div className="border-gray-200 border-b bg-gray-50 px-4 py-4 sm:px-4">
                      <div className="w-full">
                        <Dialog.Title className="text-base leading-6">{title}</Dialog.Title>
                      </div>
                    </div>
                    {children}
                  </Dialog.Panel>
                </Transition.Child>
              </div>
            </div>
          </div>
        </Dialog>
      </Transition.Root>

      <ModalConfirm
        title="Closing form"
        description="Are you sure you want to close this form? All unsaved changes will be lost."
        onConfirm={() => setPreventClose(false)}
        isOpen={!open && !!previousOpen && preventClose}
        onOpenChange={(isOpen) => {
          if (!isOpen) setOpen(true);
        }}
      />
    </SlideOverContext>
  );
}

type SlideOverTitleProps = {
  schema: ModelSchema;
  currentObjectLabel?: string | null;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
};

export const SlideOverTitle = ({
  currentObjectLabel,
  schema,
  title,
  subtitle,
}: SlideOverTitleProps) => {
  const { currentBranch } = useCurrentBranch();

  return (
    <div className="space-y-2">
      <div className="flex">
        <Badge variant="blue" className="flex items-center gap-1">
          <Icon icon="mdi:layers-triple" />
          <span>{currentBranch.name}</span>
        </Badge>

        <ObjectHelpButton
          kind={schema.kind}
          documentationUrl={schema.documentation}
          className="ml-auto"
        />
      </div>

      <div className="flex justify-between">
        <div className="flex w-full items-center gap-2 whitespace-nowrap text-sm">
          {schema.label}

          {currentObjectLabel && (
            <>
              <Icon icon="mdi:chevron-right" />

              <span className="truncate">{currentObjectLabel}</span>
            </>
          )}
        </div>
      </div>

      <div>
        {title && <h3 className="font-semibold text-lg">{title}</h3>}
        {subtitle && <p className="text-sm">{subtitle}</p>}
      </div>
    </div>
  );
};
