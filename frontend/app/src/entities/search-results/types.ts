export type SearchResultItem = {
  id: string;
  kind: string;
};

export type SearchResultsGroup = {
  kind: string;
  label: string;
  count: number;
  results: SearchResultItem[];
};
