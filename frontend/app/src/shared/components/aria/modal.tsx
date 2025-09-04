import { cva } from "class-variance-authority";
import {
  Heading as AriaHeading,
  HeadingProps as AriaHeadingProps,
  Modal as AriaModal,
  ModalOverlayProps as AriaModalOverlayProps,
  composeRenderProps,
} from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export const modalStyle = cva(
  [
    "-translate-x-1/2 -translate-y-1/2 fixed top-1/2 left-1/2 z-50",
    "rounded-lg border border-neutral-300 bg-white p-6 shadow-lg duration-200",
    "max-h-[calc(100%-2rem)] max-w-[calc(100%-2rem)]",
  ],
  {
    variants: {
      isEntering: {
        true: "fade-in-0 zoom-in-95 animate-in",
      },
      isExiting: {
        true: "fade-out-0 zoom-out-95 animate-out",
      },
    },
  }
);

interface ModalProps extends AriaModalOverlayProps {}

export function Modal({ className, ...props }: ModalProps) {
  return (
    <AriaModal
      className={composeRenderProps(className, (className, renderProps) =>
        modalStyle({ ...renderProps, className })
      )}
      {...props}
    />
  );
}

export function ModalTitle({ className, ...props }: AriaHeadingProps) {
  return (
    <AriaHeading
      slot="title"
      className={classNames("font-semibold text-lg leading-none tracking-tight", className)}
      {...props}
    />
  );
}
