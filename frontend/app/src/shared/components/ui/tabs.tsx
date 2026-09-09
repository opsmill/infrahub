import * as TabsPrimitive from "@radix-ui/react-tabs";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export const Tabs = TabsPrimitive.Root;

/**
 * `underline` is the original look: triggers sized to their label, sitting on a bottom rule that
 * the active one breaks through — a strip that separates what is above it from what is below.
 *
 * `field` is for tabs that switch how one form field is filled in. It carries no track, border or
 * rule of its own: inside a field the *label* is the separation, so a boxed or ruled strip would
 * compete with it and read as a second divider. Equal-width triggers span the field, and only the
 * selected one is tinted, just enough to say which panel is showing.
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
        ? // No rule of its own: the inactive triggers draw it, so it breaks where the active one
          // sits. No gap either, or the rule would break between triggers too.
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
            // 1px reserved on all four sides so switching tabs cannot shift the strip's height;
            // only the edges that should show are given a colour. A size down from the base:
            // the strip labels a control, it is not a heading.
            "flex-1 rounded-t-md border border-transparent text-foreground-muted text-xs",
            // Inactive triggers carry the rule…
            "data-[state=inactive]:border-b-border",
            // …and the active one is a folder tab: sides and top drawn, bottom left open so it
            // reads as continuous with the panel beneath it.
            "data-[state=active]:border-x-border data-[state=active]:border-t-border",
            "data-[state=active]:text-foreground",
          ]
        : [
            "rounded-t-md",
            // The active trigger overlaps the list's bottom border, so it reads as attached to its panel.
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
