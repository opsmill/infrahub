import type { ReactNode } from "react";

import {
  Tooltip as AriaTooltip,
  type TooltipProps as AriaTooltipProps,
  composeRenderProps,
  OverlayArrow,
  TooltipTrigger,
} from "react-aria-components";
import { tv } from "tailwind-variants";

export interface TooltipProps extends Omit<AriaTooltipProps, "children"> {
  children: ReactNode;
  message: ReactNode;
}

const tooltipStyles = tv({
  base: "group box-border rounded-xl border border-neutral-800 bg-neutral-700 px-2 py-1 font-sans text-white text-xs drop-shadow-lg will-change-transform",
  variants: {
    isEntering: {
      true: "fade-in data-[placement=bottom]:slide-in-from-top-0.5 data-[placement=top]:slide-in-from-bottom-0.5 data-[placement=left]:slide-in-from-right-0.5 data-[placement=right]:slide-in-from-left-0.5 animate-in duration-200 ease-out",
    },
    isExiting: {
      true: "fade-out data-[placement=bottom]:slide-out-to-top-0.5 data-[placement=top]:slide-out-to-bottom-0.5 data-[placement=left]:slide-out-to-right-0.5 data-[placement=right]:slide-out-to-left-0.5 animate-out duration-150 ease-in",
    },
  },
});

/** Accessible tooltip. Wraps a trigger child and shows `message` on hover/focus. */
export function Tooltip({
  children,
  message,
  isOpen,
  onOpenChange,
  className,
  ...props
}: TooltipProps) {
  const hasMessage = !message && message !== 0;
  if (!hasMessage) {
    return children;
  }

  return (
    <TooltipTrigger
      delay={200}
      closeDelay={300}
      shouldCloseOnPress={false}
      isOpen={isOpen}
      onOpenChange={onOpenChange}
    >
      {children}

      <AriaTooltip
        offset={10}
        {...props}
        className={composeRenderProps(className, (resolvedClassName, renderProps) =>
          tooltipStyles({ ...renderProps, className: resolvedClassName }),
        )}
      >
        <OverlayArrow>
          <svg
            width={8}
            height={8}
            viewBox="0 0 8 8"
            className="block fill-neutral-700 stroke-neutral-800 group-data-[placement=bottom]:rotate-180 group-data-[placement=left]:-rotate-90 group-data-[placement=right]:rotate-90"
          >
            <path d="M0 0 L4 4 L8 0" />
          </svg>
        </OverlayArrow>
        {message}
      </AriaTooltip>
    </TooltipTrigger>
  );
}
