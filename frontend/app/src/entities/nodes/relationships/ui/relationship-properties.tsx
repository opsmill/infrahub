import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { PropertyList } from "@/shared/components/table/property-list";
import { Link } from "@/shared/components/ui/link";
import { formatFullDate } from "@/shared/utils/date";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import {
  type UseGetRelationshipPropertiesParams,
  useGetRelationshipProperties,
} from "@/entities/nodes/relationships/domain/get-relationship-properties/get-relationship-properties.query";

export interface RelationshipPropertiesProps extends UseGetRelationshipPropertiesParams {}

export function RelationshipProperties(props: RelationshipPropertiesProps) {
  const { data, isPending, error } = useGetRelationshipProperties(props);

  if (isPending) {
    return <LoadingIndicator message="Loading relationship properties..." />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching relationship properties" />;
  }

  const { source, owner, updated_at, is_protected, is_visible } = data;

  const items = [
    {
      name: "Source",
      value: source ? (
        <Link to={constructPath(`/objects/${source.__typename}/${source.id}`)}>
          {getNodeLabel(source)}
        </Link>
      ) : (
        "-"
      ),
    },
    {
      name: "Updated at",
      value: formatFullDate(updated_at),
    },
    {
      name: "Owner",
      value: owner ? (
        <Link to={constructPath(`/objects/${owner.__typename}/${owner.id}`)}>
          {getNodeLabel(owner)}
        </Link>
      ) : (
        "-"
      ),
    },
    {
      name: "Is visible",
      value: is_visible ? "True" : "False",
    },
    {
      name: "Is protected",
      value: is_protected ? "True" : "False",
    },
  ];

  return <PropertyList properties={items} valueClassName="text-right" />;
}
