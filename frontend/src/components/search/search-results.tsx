import { SearchResultItem } from "./search-result-item";

type tSearchResults = {
  results?: any;
};

export const SearchResults = (props: tSearchResults) => {
  const { results = {} } = props;

  const { count, edges = [] } = results;

  if (count === 0) {
    return <div data-testid="results-container">No results found</div>;
  }

  return (
    <div className="flex flex-col" data-testid="results-container">
      {edges.map((item: any, index: number) => (
        <SearchResultItem key={index} item={item.node} />
      ))}
    </div>
  );
};
