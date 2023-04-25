import { Disclosure } from "@headlessui/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

type AccordionProps = {
  title?: any;
  children?: any;
};

export default function Accordion(props: AccordionProps) {
  const {title, children} = props;

  return (
    <Disclosure as="div">
      {({ open }) => (
        <>
          <div>
            <Disclosure.Button className="flex w-full items-center text-left">
              <span className="flex h-7 items-center mr-2 relative">
                {
                  open
                    ? (
                      <ChevronDownIcon className="h-5 w-5" aria-hidden="true" />
                    )
                    : (
                      <ChevronRightIcon className="h-5 w-5" aria-hidden="true" />
                    )
                }

              </span>
              <span className="font-semibold">{title}</span>
            </Disclosure.Button>
          </div>

          <Disclosure.Panel as="dd" className="mt-2">
            {children}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
