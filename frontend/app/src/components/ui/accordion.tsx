"use client";

import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import * as React from "react";

export const Accordion = AccordionPrimitive.Root;

export const AccordionItem = AccordionPrimitive.Item;

export const AccordionTrigger = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <AccordionPrimitive.Header className="flex">
    <AccordionPrimitive.Trigger
      ref={ref}
      className={classNames(
        "flex flex-1 items-center py-4 font-medium transition-all [&[data-state=open]>iconify-icon]:rotate-90",
        className
      )}
      {...props}
    >
      <Icon
        icon="mdi:chevron-right"
        className="text-xl shrink-0 transition-transform duration-200"
      />
      {children}
    </AccordionPrimitive.Trigger>
  </AccordionPrimitive.Header>
));

export const AccordionContent = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <AccordionPrimitive.Content
    ref={ref}
    className="overflow-hidden text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down"
    {...props}
  >
    <div className={classNames(className)}>{children}</div>
  </AccordionPrimitive.Content>
));
