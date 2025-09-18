import type { HTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router";

import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import {
  getDisplayValue,
  type RelationshipManyType,
  type RelationshipOneType,
} from "@/entities/nodes/getObjectItemDisplayValue";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

type ObjectItemsCellProps = {
  row: any;
  attribute:
    | (RelationshipSchema & { isRelationship: true; paginated: boolean })
    | (AttributeSchema & { isAttribute: boolean });
};

export const ObjectItemsCell = ({ row, attribute }: ObjectItemsCellProps) => {
  if ("isRelationship" in attribute && attribute.isRelationship) {
    if (attribute.cardinality === "one") {
      return <RelationshipOneCell data={row[attribute.name]} />;
    }

    if (attribute.cardinality === "many") {
      return <RelationshipManyCell data={row[attribute.name]} />;
    }
  }

  const url = getObjectDetailsUrl(row.__typename, row.id);

  return <LinkCell to={url}>{getDisplayValue(row, attribute)}</LinkCell>;
};

export const TextCell = ({ className, ...props }: HTMLAttributes<HTMLSpanElement>) => {
  return (
    <span className={classNames("whitespace-nowrap px-4 py-2 text-xs", className)} {...props} />
  );
};

export const LinkCell = ({ className, children, ...props }: LinkProps) => {
  return (
    <Link className={classNames("flex h-full items-center", className)} {...props}>
      <TextCell>{children}</TextCell>
    </Link>
  );
};

export const RelationshipOneCell = ({ data }: { data: RelationshipOneType }) => {
  if (!data.node) return <TextCell>-</TextCell>;

  return (
    <LinkCell
      to={getObjectDetailsUrl(data.node.__typename, data.node.id)}
      className="hover:underline"
    >
      {data.node.display_label}
    </LinkCell>
  );
};

export const RelationshipManyCell = ({ data }: { data: RelationshipManyType }) => {
  return (
    <div className="flex flex-wrap gap-1 px-1 py-2">
      {data.edges.map(({ node }) => {
        if (!node) return null;

        return (
          <Link key={node.id} to={getObjectDetailsUrl(node.__typename, node.id)}>
            <Badge className="font-medium hover:bg-gray-200 hover:underline">
              {node.display_label}
            </Badge>
          </Link>
        );
      })}
    </div>
  );
};
