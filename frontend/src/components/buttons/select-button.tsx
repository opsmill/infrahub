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
          <div className="flex flex-1 overflow-hidden">
            <div className="flex flex-1 shadow-sm overflow-hidden">
              <Listbox.Button
                className="flex-1 rounded-l-md border border-transparent overflow-hidden"
                as={Button}
                buttonType={BUTTON_TYPES.MAIN}
                data-cy="branch-list-display-button"
                data-testid="branch-list-display-button">
                <div className="flex flex-1 items-center py-2 pr-1 text-custom-white truncate">
                  {valueLabel}
                </div>

                <Icon icon="mdi:chevron-down" className="tetx-custom-white" />
              </Listbox.Button>
            </div>

            <Transition
              show={open}
              as={Fragment}
              leave="transition ease-in duration-100"
              leaveFrom="opacity-100"
              leaveTo="opacity-0">
              <Listbox.Options
                className="absolute z-10 w-72 divide-y divide-gray-200 bg-custom-white shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none rounded-md max-h-[300px] overflow-auto"
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
