import * as TabsPrimitive from "@radix-ui/react-tabs";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export const Tabs = TabsPrimitive.Root;

/**
 * `underline`: triggers sized to their label on a bottom rule the active one breaks through.
 * `field`: for tabs inside a form field, where the label is already the separation, so the strip
 * carries no track, border or rule of its own.
 */
export type TabsVariant = "underline" | "field";

export interface TabsListProps extends React.ComponentProps<typeof TabsPrimitive.List> {
  variant?: TabsVariant;
}

export const TabsList = ({ className, ref, variant = "underline", ...props }: TabsListProps) => (
  <TabsPrimitive.List
    ref={ref}
    className={classNames(
      variant === "field"
        ? // No rule and no gap of its own: the inactive triggers draw it, so it breaks only where the active one sits.
          "flex w-full items-center"
        : "inline-flex items-center border-b",
      className
    )}
    {...props}
  />
);

export interface TabsTriggerProps extends React.ComponentProps<typeof TabsPrimitive.Trigger> {
  variant?: TabsVariant;
}

export const TabsTrigger = ({
  className,
  ref,
  variant = "underline",
  ...props
}: TabsTriggerProps) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={classNames(
      "inline-flex items-center justify-center whitespace-nowrap px-3 py-1.5 font-medium text-sm transition-all",
      "outline-hidden",
      "disabled:pointer-events-none disabled:opacity-50",
      variant === "field"
        ? [
            // 1px reserved on all four sides so switching tabs cannot shift the strip's height.
            "flex-1 rounded-t-md border border-transparent text-foreground-muted text-xs",
            "data-[state=inactive]:border-b-border",
            "data-[state=active]:border-x-border data-[state=active]:border-t-border",
            "data-[state=active]:text-foreground",
          ]
        : [
            "rounded-t-md",
            "data-[state=active]:-mb-px data-[state=active]:border-x data-[state=active]:border-t",
          ],
      className
    )}
    {...props}
  />
);

export interface TabsContentProps extends React.ComponentProps<typeof TabsPrimitive.Content> {}

export const TabsContent = ({ className, ref, ...props }: TabsContentProps) => (
  <TabsPrimitive.Content
    ref={ref}
    tabIndex={-1}
    className={classNames("outline-hidden", className)}
    {...props}
  />
);
