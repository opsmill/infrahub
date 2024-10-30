"use client";

import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import * as React from "react";

export const Accordion = AccordionPrimitive.Root;

export const AccordionItem = AccordionPrimitive.Item;

export const AccordionTrigger = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Trigger> & { iconClassName?: string }
>(({ className, children, iconClassName, ...props }, ref) => (
  <AccordionPrimitive.Header className="flex">
    <AccordionPrimitive.Trigger
      ref={ref}
      className={classNames(
        "flex flex-1 items-center py-4 font-medium transition-all [&[data-state=open]>div>iconify-icon]:rotate-90",
        className
      )}
      {...props}
    >
      {children}

      <div className={classNames("flex ml-auto rounded p-1", iconClassName)}>
        <Icon
          icon="mdi:chevron-right"
          className="text-xl shrink-0 transition-transform duration-200"
        />
      </div>
    </AccordionPrimitive.Trigger>
  </AccordionPrimitive.Header>
));

export const AccordionContent = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Content>
>(({ className, children, style, ...props }, ref) => (
  <AccordionPrimitive.Content
    ref={ref}
    className="overflow-hidden text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down"
    {...props}
  >
    <div className={classNames(className)} style={style}>
      {children}
    </div>
  </AccordionPrimitive.Content>
));
