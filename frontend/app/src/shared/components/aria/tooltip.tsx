import { cva } from "class-variance-authority";
import type React from "react";
import {
  Tooltip as AriaTooltip,
  type TooltipProps as AriaTooltipProps,
  composeRenderProps,
  OverlayArrow,
  TooltipTrigger,
} from "react-aria-components";

export interface TooltipProps extends Omit<AriaTooltipProps, "children"> {
  children: React.ReactNode;
}

const styles = cva(
  "group box-border rounded-xl border border-neutral-800 bg-neutral-700 px-2 py-1 font-sans text-white text-xs drop-shadow-lg will-change-transform",
  {
    variants: {
      isEntering: {
        true: "fade-in placement-bottom:slide-in-from-top-0.5 placement-top:slide-in-from-bottom-0.5 placement-left:slide-in-from-right-0.5 placement-right:slide-in-from-left-0.5 animate-in duration-200 ease-out",
      },
      isExiting: {
        true: "fade-out placement-bottom:slide-out-to-top-0.5 placement-top:slide-out-to-bottom-0.5 placement-left:slide-out-to-right-0.5 placement-right:slide-out-to-left-0.5 animate-out duration-150 ease-in",
      },
    },
  }
);

export function Tooltip({
  children,
  message,
  isOpen,
  onOpenChange,
  ...props
}: TooltipProps & { message: React.ReactNode }) {
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
        {...props}
        offset={10}
        className={composeRenderProps(props.className, (className, renderProps) =>
          styles({ ...renderProps, className })
        )}
      >
        <OverlayArrow>
          <svg
            width={8}
            height={8}
            viewBox="0 0 8 8"
            className="block fill-neutral-700 stroke-neutral-800 group-placement-bottom:rotate-180 group-placement-left:-rotate-90 group-placement-right:rotate-90"
          >
            <path d="M0 0 L4 4 L8 0" />
          </svg>
        </OverlayArrow>
        {message}
      </AriaTooltip>
    </TooltipTrigger>
  );
}
