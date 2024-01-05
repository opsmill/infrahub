import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/20/solid";
import { useState } from "react";
import { Button } from "../../components/buttons/button";
import { BADGE_TYPES, Badge } from "../../components/display/badge";
import { iComboBoxFilter } from "../../graphql/variables/filtersVar";
import useFilters from "../../hooks/useFilters";
import DeviceFilterBarContent from "./device-filter-bar-content";

// const sortOptions = [
//   { name: "Name", href: "#", current: true },
//   { name: "Status", href: "#", current: false },
//   { name: "ASN", href: "#", current: false },
// ];

// TODO: Functionnal programming update
// TODO: Pagination with infitie scrolling for the select
export default function DeviceFilterBar(props: any) {
  const { objectname } = props;

  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useFilters();

  const handleClickReset = () => {
    setFilters();
  };

  const handleClickRemoveFilter = (filter: any) => {
    const newFilters = filters.filter((row: iComboBoxFilter) => row !== filter);

    setFilters(newFilters);
  };

  return (
    <div className="bg-custom-white">
      <div
        aria-labelledby="filter-heading"
        className="grid items-center border-t border-b border-gray-200">
        <h2 id="filter-heading" className="sr-only">
          Filters
        </h2>
        <div className="bg-gray-100">
          <div className="p-4 flex items-center">
            <div className="flex space-x-6 divide-x divide-gray-200 text-sm">
              <div className="group flex items-center align-middle font-medium text-custom-blue-700">
                {filters.length} Filters
              </div>
              <div className="pl-4">
                <Button onClick={handleClickReset}>Clear all</Button>
              </div>
            </div>
            <div aria-hidden="true" className="hidden h-5 w-px bg-gray-300 sm:ml-4 sm:block" />
            <div className="mt-2 flex-1 sm:mt-0 sm:ml-4">
              <div className="-m-1 flex flex-wrap items-center">
                {filters.map((filter: iComboBoxFilter, index: number) => (
                  <Badge
                    key={index}
                    onDelete={() => handleClickRemoveFilter(filter)}
                    vaue={filter}
                    type={BADGE_TYPES.LIGHT}>
                    {filter.display_label}: {filter.value}
                  </Badge>
                ))}
              </div>
            </div>

            {!showFilters && (
              <ChevronRightIcon
                onClick={() => setShowFilters(true)}
                className="w-4 h-4 cursor-pointer text-gray-500"
              />
            )}
            {showFilters && (
              <ChevronDownIcon
                onClick={() => setShowFilters(false)}
                className="w-4 h-4 cursor-pointer text-gray-500"
              />
            )}

            {/* Sort Options Dropdown */}
            {/* <div className="flex justify-end">
              <Menu as="div" className="relative inline-block">
                <div className="flex">
                  <Menu.Button className="group inline-flex justify-center text-sm font-medium text-gray-700 hover:text-gray-900">
                    Sort
                    <ChevronDownIcon
                      className="-mr-1 ml-1 w-4 h-4 flex-shrink-0 text-gray-400 group-hover:text-gray-500"
                      aria-hidden="true"
                    />
                  </Menu.Button>
                </div>

                <Transition
                  as={Fragment}
                  enter="transition ease-out duration-100"
                  enterFrom="transform opacity-0 scale-95"
                  enterTo="transform opacity-100 scale-100"
                  leave="transition ease-in duration-75"
                  leaveFrom="transform opacity-100 scale-100"
                  leaveTo="transform opacity-0 scale-95"
                >
                  <Menu.Items className="absolute right-0 z-20 mt-2 w-40 origin-top-right rounded-md bg-custom-white shadow-2xl ring-1 ring-custom-black ring-opacity-5 focus:outline-none">
                    <div className="py-1">
                      {
                        sortOptions
                        .map(
                          (option) => (
                            <Menu.Item key={option.name}>
                              {
                                ({ active }) => (
                                  <a
                                    href={option.href}
                                    className={classNames(
                                      option.current
                                        ? "font-medium text-gray-900"
                                        : "text-gray-500",
                                      active ? "bg-gray-100" : "",
                                      "block px-4 py-2 text-sm"
                                    )}
                                  >
                                    {option.name}
                                  </a>
                                )
                              }
                            </Menu.Item>
                          )
                        )
                      }
                    </div>
                  </Menu.Items>
                </Transition>
              </Menu>
            </div> */}
          </div>
        </div>

        {showFilters && <DeviceFilterBarContent objectname={objectname} />}
      </div>
    </div>
  );
}
