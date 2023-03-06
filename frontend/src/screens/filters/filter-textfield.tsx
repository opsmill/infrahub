import { useAtom } from "jotai";
import { comboxBoxFilterState } from "../../state/atoms/filters.atom";
import { components } from "../../infraops";
import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  filter: components["schemas"]["FilterSchema"];
}

export default function FilterTextField(props: Props) {
  const { filter } = props;
  const [filters, setFilters] = useAtom(comboxBoxFilterState);
  const [value, setValue] = useState("");
  const currentFilter = filters.filter((row) => row.name === filter.name);

  const updateFilter = () => {
    if (value) {
      setFilters([
        ...filters.filter((row) => row.name !== filter.name),
        {
          value,
          display_label: `${filter.name}: ${value}`,
          name: filter.name,
        },
      ]);
    } else {
      setFilters([...filters.filter((row) => row.name !== filter.name)]);
    }
  };

  return (
    <div>
      <label
        htmlFor="email"
        className="block text-sm font-medium leading-6 text-gray-900"
      >
        {filter.name}
      </label>
      <div className="mt-2">
        <input
          value={value}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              updateFilter();
            }
          }}
          onChange={(e) => {
            setValue(e.target.value);
          }}
          name={filter.name}
          id={filter.name}
          className="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 px-2"
          placeholder={"  " + filter.name}
        />
      </div>
    </div>
  );
}
