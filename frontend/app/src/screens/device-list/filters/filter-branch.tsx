import { classNames } from "@/utils/common";
import { Combobox } from "@headlessui/react";
import { CheckIcon, ChevronUpDownIcon } from "@heroicons/react/20/solid";
import { ShareIcon } from "@heroicons/react/24/outline";
import { useState } from "react";

interface Branch {
  name: string;
}

const branches: Branch[] = [
  {
    name: "main",
  },
  {
    name: "cr1245",
  },
  {
    name: "cr1281",
  },
  {
    name: "cr3720",
  },
  {
    name: "cr1246",
  },
  {
    name: "cr1282",
  },
  {
    name: "cr3721",
  },
  {
    name: "cr1247",
  },
  {
    name: "cr1283",
  },
  {
    name: "cr3724",
  },
];

export default function FilterBranch() {
  const [query, setQuery] = useState("");
  const [selectedBranch, setSelectedBranch] = useState(branches[0]);

  const filteredBranches =
    query === ""
      ? branches
      : branches.filter((person) => {
          return person.name.toLowerCase().includes(query.toLowerCase());
        });

  return (
    <Combobox as="div" value={selectedBranch} onChange={setSelectedBranch}>
      <Combobox.Label className="block text-sm font-medium text-gray-700">Branch</Combobox.Label>
      <div className="relative mt-1">
        <Combobox.Input
          className="w-full rounded-md border border-gray-300 bg-custom-white py-2 pl-3 pr-10 shadow-sm focus:border-custom-blue-500 focus:outline-none focus:ring-1 focus:ring-custom-blue-500 sm:text-sm"
          onChange={(event) => setQuery(event.target.value)}
          displayValue={(branch: Branch) => {
            if (branch) {
              return `${branch.name} (2023-02-16T11:07:34)`;
            }
            return "";
          }}
        />
        <Combobox.Button className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none">
          <ChevronUpDownIcon className="w-4 h-4 text-gray-400" aria-hidden="true" />
        </Combobox.Button>

        {filteredBranches.length > 0 && (
          <Combobox.Options className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-md bg-custom-white py-1 text-base shadow-lg ring-1 ring-custom-black ring-opacity-5 focus:outline-none sm:text-sm">
            {filteredBranches.map((branch, index) => (
              <Combobox.Option
                key={index}
                value={branch}
                className={({ active }) =>
                  classNames(
                    "relative cursor-default select-none py-2.5 pl-3 pr-5",
                    active ? "bg-gray-200" : "text-gray-900"
                  )
                }>
                {({ selected }) => (
                  <>
                    <div className="flex items-center cursor-pointer ">
                      {!selected && <ShareIcon className="text-gray-600 w-4 h-4" />}

                      {selected && <CheckIcon className="text-green-600 w-4 h-4" />}

                      <span
                        className={classNames(
                          "ml-3 truncate flex-1",
                          selected ? "font-semibold" : ""
                        )}>
                        {branch.name}
                      </span>
                      <span className="text-gray-500">(2023-02-16T11:07:34)</span>
                    </div>
                  </>
                )}
              </Combobox.Option>
            ))}
          </Combobox.Options>
        )}
      </div>
    </Combobox>
  );
}
