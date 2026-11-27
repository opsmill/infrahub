import { Link } from "react-router";

import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type { ObjectResult } from "@/entities/navigation/domain/use-cases/search-anywhere";
import {
  SearchResultNodeSummary,
  SearchResultNodeSummarySkeleton,
  useGetSearchResultObject,
} from "@/entities/navigation/ui/search-anywhere/search-result-node";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";

const rowStyle = "flex items-center gap-2 rounded-md px-2 py-1.5";

export function SearchResultLink({ node }: { node: ObjectResult }) {
  const { schema, object, isPending, error } = useGetSearchResultObject(node);

  if (!schema || error) return null;

  if (isPending) {
    return (
      <li className={rowStyle}>
        <SearchResultNodeSummarySkeleton />
      </li>
    );
  }

  if (!object) return null;

  return (
    <li>
      <Link
        to={getObjectDetailsUrl(object.__typename, object.id)}
        className={classNames(
          rowStyle,
          focusVisibleStyle,
          "hover:bg-highlight hover:text-highlight-foreground"
        )}
      >
        <SearchResultNodeSummary schema={schema} object={object} attributeLayout="columns" />
      </Link>
    </li>
  );
}
