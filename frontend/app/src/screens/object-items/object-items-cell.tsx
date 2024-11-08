import { Badge } from "@/components/ui/badge";
import { AttributeSchema, RelationshipSchema } from "@/screens/schema/types";
import { classNames } from "@/utils/common";
import {
  RelationshipManyType,
  RelationshipOneType,
  getDisplayValue,
} from "@/utils/getObjectItemDisplayValue";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { HTMLAttributes } from "react";
import { Link, LinkProps } from "react-router-dom";

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

  const url = getObjectDetailsUrl2(row.__typename, row.id);

  return <LinkCell to={url}>{getDisplayValue(row, attribute)}</LinkCell>;
};

export const TextCell = ({ className, ...props }: HTMLAttributes<HTMLSpanElement>) => {
  return (
    <span className={classNames("px-4 py-2 text-xs whitespace-nowrap", className)} {...props} />
  );
};

export const LinkCell = ({ className, children, ...props }: LinkProps) => {
  return (
    <Link className={classNames("h-full flex items-center", className)} {...props}>
      <TextCell>{children}</TextCell>
    </Link>
  );
};

export const RelationshipOneCell = ({ data }: { data: RelationshipOneType }) => {
  if (!data.node) return <TextCell>-</TextCell>;

  return (
    <LinkCell
      to={getObjectDetailsUrl2(data.node.__typename, data.node.id)}
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
          <Link key={node.id} to={getObjectDetailsUrl2(node.__typename, node.id)}>
            <Badge className="hover:underline hover:bg-gray-200 font-medium">
              {node.display_label}
            </Badge>
          </Link>
        );
      })}
    </div>
  );
};
