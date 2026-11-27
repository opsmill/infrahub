import { useRef, useState } from "react";

import { Row } from "@/shared/components/container";
import { SearchInput } from "@/shared/components/inputs/search-input";
import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";
import { toPageNumber } from "@/shared/utils/table-pagination";

import { useSearchResultsParams } from "@/entities/navigation/ui/hooks/use-search-results-params";
import { SearchCaseSensitiveToggle } from "@/entities/navigation/ui/search-case-sensitive-toggle";
import { SearchResultsList } from "@/entities/navigation/ui/search-results/search-results-list";

export function SearchResults() {
  const [{ search, caseSensitive, page }, setParams] = useSearchResultsParams();
  const topRef = useRef<HTMLDivElement>(null);

  useTitle(search ? `Search results for ${search}` : "Search results");

  const goToPage = (nextPage: number) => {
    setParams({ page: nextPage });
    topRef.current?.scrollIntoView({ block: "start" });
  };

  return (
    <Content.Card className="grow">
      <div ref={topRef} />

      <Content.CardTitle
        title="Search results"
        end={
          <Row className="gap-2">
            <SearchResultsInput
              search={search}
              onSubmit={(nextSearch) => setParams({ search: nextSearch, page: null })}
            />
            <SearchCaseSensitiveToggle
              isSelected={caseSensitive}
              onChange={(nextCaseSensitive) =>
                setParams({ caseSensitive: nextCaseSensitive, page: null })
              }
            />
          </Row>
        }
      />

      <SearchResultsList
        search={search}
        caseSensitive={caseSensitive}
        page={toPageNumber(page)}
        onPageChange={goToPage}
      />
    </Content.Card>
  );
}

interface SearchResultsInputProps {
  search: string;
  onSubmit: (search: string) => void;
}

function SearchResultsInput({ search, onSubmit }: SearchResultsInputProps) {
  const [text, setText] = useState(search);
  const [shownSearch, setShownSearch] = useState(search);

  // Back and Forward change the search in the URL, which replaces the text being typed.
  if (search !== shownSearch) {
    setShownSearch(search);
    setText(search);
  }

  return (
    <SearchInput
      aria-label="Search text"
      placeholder="Search for objects and attributes"
      value={text}
      onChange={setText}
      onSubmit={(value) => onSubmit(value.trim())}
      className="w-72"
    />
  );
}
