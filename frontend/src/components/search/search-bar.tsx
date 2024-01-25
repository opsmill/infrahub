import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { NODE_OBJECT } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { searchQuery } from "../../graphql/queries/objects/search";
import LoadingScreen from "../../screens/loading-screen/loading-screen";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { debounce } from "../../utils/common";
import { Background } from "../display/background";
import { POPOVER_SIZE, PopOver } from "../display/popover";
import { Input } from "../inputs/input";
import Transition from "../utils/transition";
import { SearchResults } from "./search-results";

type tSearchInput = {
  loading?: boolean;
  onChange: Function;
};

const SearchInput = (props: tSearchInput) => {
  const { loading, onChange } = props;

  const [search, setSearch] = useState("");

  const handleChange = (value: string) => {
    setSearch(value);
    onChange(value);
  };

  const handleFocus = () => {
    if (!search) return;

    // Will repoen the results for the current search
    onChange(search, true);
  };

  return (
    <div className="flex flex-1 items-center justify-center relative px-8 sm:px-4">
      <div className="flex flex-1 items-center justify-center relative max-w-[600px] z-20">
        <Input
          value={search}
          onChange={handleChange}
          data-testid="search-bar"
          className="py-2 pl-10 placeholder-gray-500"
          placeholder="Search"
          onFocus={handleFocus}
        />

        {loading && <LoadingScreen hideText size={20} className="absolute left-4" />}

        {!loading && <Icon icon={"mdi:magnify"} className="absolute left-4 text-custom-blue-10" />}
      </div>
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

  const handleSearch = async (newValue: string) => {
    try {
      // Set search to set open / close if empty
      setSearch(newValue);

      if (!newValue) return;

      setIsLoading(true);

      const { data }: any = await graphqlClient.query({
        query: searchQuery,
        variables: {
          search: newValue,
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
        <Background onClick={handleClick} />
      </Transition>

      <SearchInput loading={isLoading} onChange={handleChange} />

      <Transition show={isOpen}>
        <PopOver
          static
          open={isOpen}
          width={POPOVER_SIZE.NONE}
          height={POPOVER_SIZE.NONE}
          maxHeight={POPOVER_SIZE.MEDIUM}
          className="!left-0 !right-0 !top-14 z-20">
          {() => <SearchResults results={results} />}
        </PopOver>
      </Transition>
    </div>
  );
};
