import {
  Toolbar as AriaToolbar,
  type ToolbarProps as AriaToolbarProps,
  Separator,
  type SeparatorProps,
} from "react-aria-components";
import { cn } from "tailwind-variants";

export interface ToolbarProps extends Omit<AriaToolbarProps, "className"> {
  "aria-label": string;
  className?: string;
}

/** Floating toolbar container. Built on react-aria's Toolbar: one tab stop with
 *  arrow-key navigation between controls, per the WAI-ARIA toolbar pattern. */
export function Toolbar({ className, ...props }: ToolbarProps) {
  return (
    <AriaToolbar
      className={cn(
        "flex items-center gap-2 rounded-xl border bg-popover px-3 py-2 shadow-xl backdrop-blur-lg",
        className
      )}
      {...props}
    />
  );
}

export interface ToolbarDividerProps extends Omit<SeparatorProps, "className"> {
  className?: string;
}

function ToolbarDivider({ className, ...props }: ToolbarDividerProps) {
  return (
    <Separator
      orientation="vertical"
      className={cn("h-6 w-px border-0 bg-border", className)}
      {...props}
    />
  );
}

Toolbar.Divider = ToolbarDivider;
