import { Icon } from "@iconify-icon/react";
import { type CSSProperties, useState } from "react";

import { classNames } from "@/shared/utils/common";

export type AccordionProps = {
  title?: any;
  children?: any;
  className?: string;
  titleClassName?: string;
  iconClassName?: string;
  defaultOpen?: boolean;
  style?: CSSProperties;
  hideChevron?: boolean;
};

export default function Accordion({
  title,
  defaultOpen = false,
  children,
  className,
  hideChevron,
  iconClassName,
  titleClassName,
  ...props
}: AccordionProps) {
  const [isOpen, setIsOpen] = useState<boolean>();

  const open = isOpen === undefined ? defaultOpen : isOpen;

  return (
    <div className={className} {...props}>
      <div className="relative flex cursor-pointer items-center" onClick={() => setIsOpen(!open)}>
        <span
          className={classNames(
            "relative mx-2 flex items-center",
            hideChevron && "text-transparent",
            iconClassName
          )}
        >
          {open ? <Icon icon={"mdi:chevron-down"} /> : <Icon icon={"mdi:chevron-right"} />}
        </span>

        <span className={classNames("flex-1 justify-start text-left font-semibold")}>{title}</span>
      </div>

      {open && children}
    </div>
  );
}
