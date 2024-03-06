import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
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
          <span className="flex h-7 items-center mr-2 relative">
            {isOpen ? (
              <ChevronDownIcon className="w-4 h-4" aria-hidden="true" />
            ) : (
              <ChevronRightIcon className="w-4 h-4" aria-hidden="true" />
            )}
          </span>
          <span className="flex-1 font-semibold text-left justify-start">{title}</span>
        </div>
      </div>
      {isOpen && children}
    </div>
  );
}
