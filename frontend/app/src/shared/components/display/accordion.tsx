import { Icon } from "@iconify-icon/react";
import { type CSSProperties, type Ref, useState } from "react";

import { classNames } from "@/shared/utils/common";

export type AccordionProps = {
  title?: any;
  children?: any;
  className?: string;
  titleClassName?: string;
  iconClassName?: string;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  style?: CSSProperties;
  hideChevron?: boolean;
  ref?: Ref<HTMLDivElement>;
};

export default function Accordion({
  title,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  children,
  className,
  hideChevron,
  iconClassName,
  titleClassName,
  ref,
  ...props
}: AccordionProps) {
  const [internalOpen, setInternalOpen] = useState<boolean>();

  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : (internalOpen ?? defaultOpen);

  const toggle = () => {
    const next = !open;
    if (!isControlled) setInternalOpen(next);
    onOpenChange?.(next);
  };

  return (
    <div ref={ref} className={className} {...props}>
      <div className="relative flex cursor-pointer items-center" onClick={toggle}>
        <span
          className={classNames(
            "relative mx-2 flex items-center",
            hideChevron && "text-transparent",
            iconClassName
          )}
        >
          {open ? <Icon icon={"mdi:chevron-down"} /> : <Icon icon={"mdi:chevron-right"} />}
        </span>

        <span className="flex-1 justify-start text-left font-semibold">{title}</span>
      </div>

      {open && children}
    </div>
  );
}
