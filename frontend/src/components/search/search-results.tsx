import { useAtomValue } from "jotai";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { constructPath } from "../../utils/fetch";
import { Link } from "../utils/link";
import { SearchResultItem } from "./search-result-item";

type tSearchResults = {
  results?: any;
};

export const SearchResults = (props: tSearchResults) => {
  const { results = {} } = props;

  const schemaKindName = useAtomValue(schemaKindNameState);

  const { count, edges = [] } = results;

  if (count === 0) {
    return <div data-testid="results-container">No results found</div>;
  }

  const sortedResults: { [id: string]: any } = edges
    .map((item: any) => item.node)
    .reduce((acc: any, node: any) => {
      return {
        ...acc,
        [node.__typename]: [...(acc[node.__typename] ?? []), node],
      };
    }, {});

  return (
    <div className="flex flex-col" data-testid="results-container">
      {Object.entries(sortedResults).map(([kind, nodes]) => (
        <>
          <div>
            {nodes.map((node: any, index: number) => (
              <SearchResultItem key={index} item={node} />
            ))}
          </div>

          <div className="flex items-start my-4">
            <Link
              to={constructPath(`/objects/${kind}`)}
              // target="_blank"
              className="p-2 flex items-center text-xs">
              Link to all {schemaKindName[kind]}s
              {/* <Icon icon="mdi:open-in-new" className="ml-2" /> */}
            </Link>
          </div>
        </>
      ))}
    </div>
  );
};
