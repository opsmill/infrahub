import { useEffect, useState } from "react";
import { fetchUrl } from "../../utils/fetch";
import { SearchGroup, SearchGroupTitle, SearchResultItem } from "./search-modal";
import { CONFIG, INFRAHUB_API_SERVER_URL } from "../../config/config";
import { Icon } from "@iconify-icon/react";
import { useDebounce } from "../../hooks/useDebounce";

type SearchProps = {
  query: string;
};
export const SearchDocs = ({ query }: SearchProps) => {
  const queryDebounced = useDebounce(query, 300);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let ignore = false;
    const cleanedValue = queryDebounced.trim();

    fetchUrl(CONFIG.SEARCH_URL(cleanedValue))
      .then((data) => {
        if (ignore) return;
        setResults(data);
        setError(null);
      })
      .catch((error) => {
        setError(error);
      });

    return () => {
      ignore = true;
    };
  }, [queryDebounced]);

  if (error || results.length === 0)
    return (
      <SearchGroup>
        <SearchResultItem to={`${INFRAHUB_API_SERVER_URL}/docs/search?q=${query}`} target="_blank">
          <Icon icon="mdi:book-open-blank-variant-outline" className="text-lg" />
          Search in docs: <span className="font-semibold">{query}</span>
        </SearchResultItem>
      </SearchGroup>
    );

  return (
    <SearchGroup>
      <SearchGroupTitle>Documentation</SearchGroupTitle>

      {results.map((doc: SearchDocsResultProps) => (
        <DocsResults key={doc.url} breadcrumb={doc.breadcrumb} title={doc.title} url={doc.url} />
      ))}
    </SearchGroup>
  );
};

type SearchDocsResultProps = {
  breadcrumb: string[];
  title: string;
  url: string;
};

const DocsResults = ({ breadcrumb, title, url }: SearchDocsResultProps) => {
  return (
    <SearchResultItem to={INFRAHUB_API_SERVER_URL + url} target="_blank">
      {breadcrumb.slice(1).map((b) => (
        <>
          <span>{b}</span>
          <Icon icon="mdi:chevron-right" />
        </>
      ))}{" "}
      <strong className="font-semibold">{title}</strong>
    </SearchResultItem>
  );
};
