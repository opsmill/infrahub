import type { HTMLAttributes } from "react";
import { cn } from "tailwind-variants";

export interface ToolbarProps extends HTMLAttributes<HTMLDivElement> {
  "aria-label": string;
}

export function Toolbar({ className, ...props }: ToolbarProps) {
  return (
    <div
      role="toolbar"
      className={cn(
        "flex items-center gap-2 rounded-lg bg-white px-3 py-2 shadow-lg",
        className,
      )}
      {...props}
    />
  );
}

export type ToolbarDividerProps = HTMLAttributes<HTMLDivElement>;

function ToolbarDivider({ className, ...props }: ToolbarDividerProps) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      className={cn("h-6 w-px bg-gray-200", className)}
      {...props}
    />
  );
}

Toolbar.Divider = ToolbarDivider;
