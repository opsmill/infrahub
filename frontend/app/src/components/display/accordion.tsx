import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { CSSProperties, useState } from "react";

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
      <div className="flex items-center cursor-pointer relative" onClick={() => setIsOpen(!open)}>
        <span
          className={classNames(
            "flex items-center mx-2 relative",
            hideChevron && "text-transparent",
            iconClassName
          )}
        >
          {open ? <Icon icon={"mdi:chevron-down"} /> : <Icon icon={"mdi:chevron-right"} />}
        </span>

        <span className={classNames("flex-1 font-semibold text-left justify-start")}>{title}</span>
      </div>

      {open && children}
    </div>
  );
}
