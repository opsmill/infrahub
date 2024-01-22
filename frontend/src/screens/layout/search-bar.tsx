import { Icon } from "@iconify-icon/react";
import { Input } from "../../components/inputs/input";
import { useState } from "react";

export const SearchBar = () => {
  const [query, setQuery] = useState("");

  return (
    <div className="flex flex-1 items-center relative">
      <Input
        value={query}
        onChange={setQuery}
        id="search-bar"
        className="h-full w-full !rounded-none !ring-transparent py-2 pl-8 placeholder-gray-500 focus:border-transparent focus:outline-none focus:ring-0"
        placeholder="Search"
      />
      <Icon icon={"mdi:magnify"} className="absolute left-2 text-custom-blue-10" />
    </div>
  );
};
