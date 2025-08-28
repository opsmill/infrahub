import { classNames } from "@/shared/utils/common";
import { cva } from "class-variance-authority";
import {
  Heading as AriaHeading,
  HeadingProps as AriaHeadingProps,
  Modal as AriaModal,
  ModalOverlayProps as AriaModalOverlayProps,
  composeRenderProps,
} from "react-aria-components";

export const modalStyle = cva(
  [
    "fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
    "bg-white rounded-lg p-6 shadow-lg border border-neutral-300 duration-200",
    "max-w-[calc(100%-2rem)] max-h-[calc(100%-2rem)]",
  ],
  {
    variants: {
      isEntering: {
        true: "animate-in fade-in-0 zoom-in-95",
      },
      isExiting: {
        true: "animate-out fade-out-0 zoom-out-95",
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
      className={classNames("text-lg font-semibold leading-none tracking-tight", className)}
      {...props}
    />
  );
}
