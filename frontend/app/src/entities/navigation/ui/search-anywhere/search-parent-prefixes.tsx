import { useCommandState } from "cmdk";
import { useAtomValue } from "jotai";

import { useDebounce } from "@/shared/hooks/useDebounce";

import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";
import { searchExactMatchAtom } from "@/entities/navigation/stores/search-exact-match.atom";
import { useGetSearchAnywhere } from "@/entities/navigation/ui/queries/search-anywhere.query";
import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/navigation/ui/search-anywhere/search-anywhere-item";
import {
  NodesOptions,
  SEARCH_FIRST_PAGE_SIZE,
} from "@/entities/navigation/ui/search-anywhere/search-nodes";

export const SearchParentPrefixes = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);
  const caseSensitive = useAtomValue(searchCaseSensitiveAtom);
  const exactMatch = useAtomValue(searchExactMatchAtom);

  const { data, isPending, error } = useGetSearchAnywhere(
    // The first page's request also carries the parent prefixes, so this reuses it.
    { search: queryDebounced, limit: SEARCH_FIRST_PAGE_SIZE, caseSensitive, exactMatch },
    {
      enabled: !!queryDebounced,
    }
  );

  if (!queryDebounced || isPending || error || !data?.parentPrefixes) return null;

  if (data.parentPrefixes.length === 0) {
    return (
      <SearchAnywhereGroup heading="Parent Prefixes">
        <SearchAnywhereItem to="" disabled>
          No containing prefixes found
        </SearchAnywhereItem>
      </SearchAnywhereGroup>
    );
  }

  return (
    <SearchAnywhereGroup heading="Parent Prefixes">
      {data.parentPrefixes.map((node) => (
        <NodesOptions key={node.id} node={node} />
      ))}
    </SearchAnywhereGroup>
  );
};
