import type React from "react";
import {
  Tooltip as AriaTooltip,
  type TooltipProps as AriaTooltipProps,
  composeRenderProps,
  Focusable,
  OverlayArrow,
  TooltipTrigger,
} from "react-aria-components";
import { tv } from "tailwind-variants";

export interface TooltipProps extends Omit<AriaTooltipProps, "children"> {
  children: React.ReactNode;
  message: React.ReactNode;
  /**
   * Set when the trigger is not an interactive element (span, icon, badge) so it can
   * receive hover events without becoming a tab stop. The child must be a single
   * element that accepts a ref and DOM props.
   */
  nonInteractiveTrigger?: boolean;
}

const tooltipStyles = tv({
  base: "group box-border rounded-xl border border-stone-700 bg-stone-800 px-2 py-1 font-sans text-white text-xs drop-shadow-lg will-change-transform",
  variants: {
    isEntering: {
      true: "data-[placement=bottom]:slide-in-from-top-0.5 data-[placement=top]:slide-in-from-bottom-0.5 data-[placement=left]:slide-in-from-right-0.5 data-[placement=right]:slide-in-from-left-0.5 fade-in animate-in duration-200 ease-out",
    },
    isExiting: {
      true: "data-[placement=bottom]:slide-out-to-top-0.5 data-[placement=top]:slide-out-to-bottom-0.5 data-[placement=left]:slide-out-to-right-0.5 data-[placement=right]:slide-out-to-left-0.5 fade-out animate-out duration-150 ease-in",
    },
  },
});

export function Tooltip({
  children,
  message,
  isOpen,
  onOpenChange,
  className,
  nonInteractiveTrigger,
  ...props
}: TooltipProps) {
  if (!message && message !== 0) {
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
      {nonInteractiveTrigger ? (
        <Focusable excludeFromTabOrder>
          {children as React.ComponentProps<typeof Focusable>["children"]}
        </Focusable>
      ) : (
        children
      )}

      <AriaTooltip
        offset={10}
        {...props}
        className={composeRenderProps(className, (resolvedClassName, renderProps) =>
          tooltipStyles({ ...renderProps, className: resolvedClassName })
        )}
      >
        <OverlayArrow>
          <svg
            width={8}
            height={8}
            viewBox="0 0 8 8"
            className="block fill-stone-800 stroke-stone-700 group-data-[placement=bottom]:rotate-180 group-data-[placement=left]:-rotate-90 group-data-[placement=right]:rotate-90"
          >
            <path d="M0 0 L4 4 L8 0" />
          </svg>
        </OverlayArrow>
        {message}
      </AriaTooltip>
    </TooltipTrigger>
  );
}
