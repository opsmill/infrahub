import { getObjectDetailsUrl2 } from "@/utils/objects";
import { Link } from "react-router-dom";
import {
  getObjectItemDisplayValue,
  RelationshipManyType,
  RelationshipOneType,
} from "@/utils/getObjectItemDisplayValue";
import { AttributeSchema, RelationshipSchema } from "@/screens/schema/types";
import { Badge } from "@/components/ui/badge";

type ObjectItemsCellProps = {
  row: any;
  attribute:
    | (RelationshipSchema & { isRelationship: true; paginated: boolean })
    | (AttributeSchema & { isAttribute: boolean });
};

export default function ObjectItemsCell({ row, attribute }: ObjectItemsCellProps) {
  const url = getObjectDetailsUrl2(row.__typename, row.id);

  if ("isRelationship" in attribute && attribute.isRelationship) {
    if (attribute.cardinality === "one") {
      return <RelationshipOneCell data={row[attribute.name]} />;
    }

    if (attribute.cardinality === "many") {
      return <RelationshipManyCell data={row[attribute.name]} />;
    }
  }

  return (
    <td>
      <Link to={url}>
        <div className="whitespace-wrap px-2 py-1 text-xs text-gray-900 flex items-center">
          {getObjectItemDisplayValue(row, attribute)}
        </div>
      </Link>
    </td>
  );
}

const RelationshipOneCell = ({ data }: { data: RelationshipOneType }) => {
  if (!data.node) return "-";

  return (
    <td>
      <Link
        to={getObjectDetailsUrl2(data.node.__typename, data.node.id)}
        className="hover:underline text-xs">
        {data.node.display_label}
      </Link>
    </td>
  );
};

const RelationshipManyCell = ({ data }: { data: RelationshipManyType }) => {
  return (
    <td className="space-x-1">
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
    </td>
  );
};
