import { Disclosure } from "@headlessui/react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

// type Accordion = {};

export default function Accordion(props: any) {
  const {title, children} = props;

  return (
    <Disclosure as="div">
      {({ open }) => (
        <>
          <dt>
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
          </dt>

          <Disclosure.Panel as="dd" className="mt-2 pr-12">
            {children}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
