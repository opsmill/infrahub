import { Disclosure } from "@headlessui/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

type AccordionProps = {
  title?: any;
  children?: any;
};

export default function Accordion(props: AccordionProps) {
  const { title, children } = props;

  return (
    <Disclosure as="div">
      {({ open }) => (
        <>
          <div className="flex">
            <Disclosure.Button className="flex flex-1 w-full items-center">
              <span className="flex h-7 items-center mr-2 relative">
                {open ? (
                  <ChevronDownIcon className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <ChevronRightIcon className="h-5 w-5" aria-hidden="true" />
                )}
              </span>
              <span className="flex-1 font-semibold text-left justify-start">
                {title}
              </span>
            </Disclosure.Button>
          </div>

          <Disclosure.Panel className="p-2 pl-8 pr-0">
            {children}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
