import { Listbox, Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { Fragment } from "react";
import { classNames } from "../../utils/common";
import { BUTTON_TYPES, Button } from "./button";

// type SelectButtonProps = {};

export const SelectButton = (props: any) => {
  const { label, value, valueLabel, onChange, options, renderOption } = props;

  return (
    <Listbox value={value} onChange={onChange}>
      {({ open }) => (
        <>
          <Listbox.Label className="sr-only">{label}</Listbox.Label>
          <div className="relative">
            <div className="inline-flex shadow-sm">
              <div className="inline-flex shadow-sm">
                <div className="inline-flex items-center border border-transparent bg-custom-blue-700 py-2 pl-3 pr-4 text-custom-white shadow-sm rounded-l-md">
                  {valueLabel}
                </div>
                <Listbox.Button
                  className="rounded-none border border-transparent"
                  as={Button}
                  buttonType={BUTTON_TYPES.MAIN}
                  data-cy="branch-list-display-button"
                  data-testid="branch-list-display-button">
                  <Icon icon="mdi:chevron-down" className="tetx-custom-white" />
                </Listbox.Button>
              </div>
            </div>
            <Transition
              show={open}
              as={Fragment}
              leave="transition ease-in duration-100"
              leaveFrom="opacity-100"
              leaveTo="opacity-0">
              <Listbox.Options
                className="absolute right-0 mt-2 w-72 origin-top-right divide-y divide-gray-200 overflow-hidden bg-custom-white shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none rounded-md max-h-[500px] overflow-y-auto"
                data-cy="branch-list-dropdown"
                data-testid="branch-list-dropdown">
                {options.map((option: any) => (
                  <Listbox.Option
                    key={option.name}
                    className={({ active }) =>
                      classNames(
                        active ? "text-custom-white bg-custom-blue-700" : "text-gray-900",
                        "cursor-pointer select-none p-4 text-sm"
                      )
                    }
                    value={option}>
                    {(attributes) =>
                      renderOption({
                        option,
                        ...attributes,
                      })
                    }
                  </Listbox.Option>
                ))}
              </Listbox.Options>
            </Transition>
          </div>
        </>
      )}
    </Listbox>
  );
};
