import { useCommandState } from "cmdk";
import { useAtomValue } from "jotai";

import { useDebounce } from "@/shared/hooks/useDebounce";

import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";
import { useGetSearchAnywhere } from "@/entities/navigation/ui/queries/search-anywhere.query";
import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/navigation/ui/search-anywhere/search-anywhere-item";
import { NodesOptions } from "@/entities/navigation/ui/search-anywhere/search-nodes";

export const SearchParentPrefixes = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);
  const caseSensitive = useAtomValue(searchCaseSensitiveAtom);

  const { data, isPending, error } = useGetSearchAnywhere(
    { search: queryDebounced, caseSensitive },
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
