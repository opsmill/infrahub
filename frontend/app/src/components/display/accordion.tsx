import { Icon } from "@iconify-icon/react";
import { CSSProperties, useState } from "react";

export type AccordionProps = {
  title?: any;
  children?: any;
  className?: string;
  defaultOpen?: boolean;
  style?: CSSProperties;
};

export default function Accordion({
  title,
  defaultOpen = false,
  children,
  className,
  ...props
}: AccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={className} {...props}>
      <div className="flex">
        <div
          className="flex flex-1 w-full items-center cursor-pointer"
          onClick={() => setIsOpen(!isOpen)}>
          <span className="flex h-7 items-center mx-2 relative">
            {isOpen ? <Icon icon={"mdi:chevron-down"} /> : <Icon icon={"mdi:chevron-right"} />}
          </span>
          <span className="flex-1 font-semibold text-left justify-start">{title}</span>
        </div>
      </div>
      {isOpen && children}
    </div>
  );
}
