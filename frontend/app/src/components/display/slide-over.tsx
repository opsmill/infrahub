import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { Badge } from "@/components/ui/badge";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Dialog, Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import React, { Fragment, useRef, useState } from "react";
import ModalDelete from "../modals/modal-delete";

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

  // Need to define full classes so tailwind can compile the css
  const panelWidth = "w-[400px]";

  const offestWidth: { [key: number]: string } = {
    0: "-translate-x-0",
    1: "-translate-x-[400px]",
  };

  const context = {
    isOpen: open || (!open && preventClose),
    setPreventClose: (value: boolean) => setPreventClose(value),
  };

  return (
    <SlideOverContext.Provider value={context}>
      <Transition.Root show={open || (!open && preventClose)} as={Fragment}>
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
              className="fixed inset-0 bg-black bg-opacity-40 transition-opacity"
              data-cy="side-panel-background"
              data-testid="side-panel-background"
            />
          </Transition.Child>

          <div className="before:fixed inset-0 overflow-hidden">
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
                    className={`bg-custom-white pointer-events-auto shadow-xl flex flex-col ${panelWidth} ${offestWidth[offset]}`}
                    data-testid="side-panel-container"
                  >
                    <div className="px-4 py-4 sm:px-4 bg-gray-50 border-b">
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

      <ModalDelete
        title="Closing form"
        description={"Are you sure you want to close this form? All unsaved changes will be lost."}
        onCancel={() => setOpen(true)}
        onDelete={() => setPreventClose(false)}
        open={!open && preventClose}
        setOpen={() => setPreventClose(false)}
        confirmLabel="Close"
      />
    </SlideOverContext.Provider>
  );
}

type SlideOverTitleProps = {
  schema: IModelSchema;
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
  const currentBranch = useAtomValue(currentBranchAtom);

  return (
    <div className="space-y-2">
      <div className="flex">
        <Badge variant="blue" className="flex items-center gap-1">
          <Icon icon="mdi:layers-triple" />
          <span>{currentBranch?.name}</span>
        </Badge>

        <ObjectHelpButton
          kind={schema.kind}
          documentationUrl={schema.documentation}
          className="ml-auto"
        />
      </div>

      <div className="flex justify-between">
        <div className="text-sm flex items-center gap-2 whitespace-nowrap w-full">
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
        {title && <h3 className="text-lg font-semibold">{title}</h3>}
        {subtitle && <p className="text-sm">{subtitle}</p>}
      </div>
    </div>
  );
};
