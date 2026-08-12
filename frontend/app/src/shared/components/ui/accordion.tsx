import { Icon } from "@iconify-icon/react";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export const Accordion = AccordionPrimitive.Root;

export const AccordionItem = AccordionPrimitive.Item;

interface AccordionTriggerProps extends React.ComponentProps<typeof AccordionPrimitive.Trigger> {
  iconClassName?: string;
}

export const AccordionTrigger = ({
  className,
  children,
  iconClassName,
  ref,
  ...props
}: AccordionTriggerProps) => (
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

      <div className={classNames("ml-auto flex rounded-sm p-1", iconClassName)}>
        <Icon
          icon="mdi:chevron-right"
          className="shrink-0 text-xl transition-transform duration-200"
        />
      </div>
    </AccordionPrimitive.Trigger>
  </AccordionPrimitive.Header>
);

interface AccordionContentProps extends React.ComponentProps<typeof AccordionPrimitive.Content> {}

export const AccordionContent = ({
  className,
  children,
  style,
  ref,
  ...props
}: AccordionContentProps) => (
  <AccordionPrimitive.Content
    ref={ref}
    className="overflow-hidden text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down"
    {...props}
  >
    <div className={classNames(className)} style={style}>
      {children}
    </div>
  </AccordionPrimitive.Content>
);
