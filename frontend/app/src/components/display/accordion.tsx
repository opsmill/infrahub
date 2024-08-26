import { Icon } from "@iconify-icon/react";
import { CSSProperties, useState } from "react";
import { classNames } from "@/utils/common";

export type AccordionProps = {
  title?: any;
  children?: any;
  className?: string;
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
  ...props
}: AccordionProps) {
  const [isOpen, setIsOpen] = useState<boolean>();

  const open = isOpen === undefined ? defaultOpen : isOpen;

  return (
    <div className={className} {...props}>
      <div className="flex">
        <div
          className="flex flex-1 w-full items-center cursor-pointer relative"
          onClick={() => setIsOpen(!open)}>
          <span
            className={classNames(
              "flex items-center mx-2 relative",
              hideChevron && "text-transparent",
              iconClassName
            )}>
            {open ? <Icon icon={"mdi:chevron-down"} /> : <Icon icon={"mdi:chevron-right"} />}
          </span>

          <span className="flex-1 font-semibold text-left justify-start">{title}</span>
        </div>
      </div>
      {open && children}
    </div>
  );
}
