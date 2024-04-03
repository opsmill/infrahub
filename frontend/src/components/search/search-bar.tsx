import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { NODE_OBJECT } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { SEARCH } from "../../graphql/queries/objects/search";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { classNames, debounce } from "../../utils/common";
import { Background } from "../display/background";
import { POPOVER_SIZE, PopOver } from "../display/popover";
import Transition from "../utils/transition";
import { SearchResults } from "./search-results";
import { Input } from "../ui/input";

type tSearchInput = {
  onChange: Function;
  className?: string;
  containerClassName?: string;
  loading?: boolean;
  placeholder?: string;
  testId?: string;
};

export const SearchInput = (props: tSearchInput) => {
  const {
    className = "",
    containerClassName = "",
    loading,
    onChange,
    placeholder = "Search",
    testId = "search-bar",
  } = props;

  const [search, setSearch] = useState("");

  const handleChange = (value: string) => {
    setSearch(value);
    onChange(value);
  };

  const handleFocus = () => {
    if (!search) return;

    // Will reopen the results for the current search
    onChange(search, true);
  };

  return (
    <div
      className={classNames(
        "flex flex-1 items-center relative max-w-[600px] z-20",
        containerClassName
      )}>
      <Input
        value={search}
        onChange={(e) => handleChange(e.target.value)}
        data-testid={testId}
        className={classNames("py-2 pl-10 placeholder-gray-500", className)}
        placeholder={placeholder}
        onFocus={handleFocus}
      />

      {loading && <LoadingScreen hideText size={20} className="absolute left-4" />}

      {!loading && <Icon icon={"mdi:magnify"} className="absolute left-4 text-custom-blue-10" />}
    </div>
  );
};

export const SearchBar = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState({});
  const [search, setSearch] = useState("");
  const location = useLocation();

  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const handleSearch = async (newValue: string = "") => {
    const cleanedValue = newValue.trim();

    try {
      // Set search to set open / close if empty
      setSearch(cleanedValue);

      if (!cleanedValue) return;

      setIsLoading(true);

      const { data } = await graphqlClient.query({
        query: SEARCH,
        variables: {
          search: cleanedValue,
        },
        context: {
          date,
          branch: branch?.name,
        },
      });

      setIsLoading(false);

      if (!data?.[NODE_OBJECT]) return;

      setResults(data[NODE_OBJECT]);
    } catch (e) {
      setIsLoading(false);
    }
  };

  // Debounce the query
  const debounceHandleSearch = debounce(handleSearch);

  const handleChange = (value: string, immediate?: boolean) => {
    // If immediate, triggers the search
    if (immediate) return handleSearch(value);

    // Debounces the search
    return debounceHandleSearch(value);
  };

  const handleClick = () => {
    // Closes the panel on background click
    setResults({});
  };

  useEffect(() => {
    // Close the panel on route change (when clicking an item)
    setResults({});
  }, [location]);

  // Open if there is a search and a result (even if empty)
  const isOpen = !!search && !!results?.edges;

  return (
    <div className="relative flex flex-1">
      <Transition show={isOpen}>
        <Background onClick={handleClick} className="bg-transparent" />
      </Transition>

      <div className="flex flex-1 justify-center">
        <SearchInput loading={isLoading} onChange={handleChange} />
      </div>

      <Transition show={isOpen}>
        <PopOver
          static
          fixed
          open={isOpen}
          width={POPOVER_SIZE.LARGE}
          height={POPOVER_SIZE.NONE}
          maxHeight={POPOVER_SIZE.MEDIUM}
          className="top-16 mt-4 left-1/2 transform -translate-x-1/2 ">
          {() => <SearchResults results={results} />}
        </PopOver>
      </Transition>
    </div>
  );
};
