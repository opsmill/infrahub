import { GET_IP_ADDRESS_KIND } from "@/entities/ipam/api/ip-address";
import { IpDetailsCard } from "@/entities/ipam/common/ip-details-card";
import { constructPathForIpam } from "@/entities/ipam/common/utils";
import { IPAM_ROUTE, IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import { IpamSummarySkeleton } from "@/entities/ipam/prefixes/ipam-summary-skeleton";
import { getObjectDetailsPaginated } from "@/entities/nodes/api/getObjectDetails";
import { getPermission } from "@/entities/permission/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import useQuery from "@/shared/api/graphql/useQuery";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Link } from "@/shared/components/ui/link";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router";

export default function IpAddressSummary() {
  const { objectId: ip_address } = useParams();

  const { loading, data } = useQuery(GET_IP_ADDRESS_KIND, {
    variables: {
      ids: [ip_address],
    },
  });

  if (loading || !data) return <IpamSummarySkeleton />;

  const parentLink = constructPathForIpam(IPAM_ROUTE.ADDRESSES);

  const ipAddressData = data[IP_ADDRESS_GENERIC].edges[0].node;

  return (
    <div className="flex flex-col grow">
      <div className="flex items-center mb-2">
        <Link to={parentLink}>All IP Addresses</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{ipAddressData.display_label}</span>
      </div>

      {loading && <LoadingIndicator />}

      <IpAddressSummaryContent
        ipAddressId={ipAddressData.id}
        ipAddressKind={ipAddressData.__typename}
      />
    </div>
  );
}
type IpAddressSummaryContentProps = {
  ipAddressId: string;
  ipAddressKind: string;
};
const IpAddressSummaryContent = ({ ipAddressId, ipAddressKind }: IpAddressSummaryContentProps) => {
  const { schema: ipAddressSchema } = useSchema(ipAddressKind);

  const columns = ipAddressSchema
    ? [
        ...(ipAddressSchema.attributes ?? []).map((attribute) => ({
          isAttribute: true,
          ...attribute,
        })),
        ...(ipAddressSchema.relationships ?? []).map((relationship) => ({
          isRelationship: true,
          paginated: relationship.cardinality === "many",
          ...relationship,
        })),
      ]
    : [];

  const query = gql(
    getObjectDetailsPaginated({
      objectid: ipAddressId,
      kind: ipAddressKind,
      columns,
      hasPermission: true,
    })
  );

  const { loading, data, error, refetch } = useQuery(query, {
    skip: !ipAddressKind,
    notifyOnNetworkStatusChange: true,
  });

  if (loading || !data || !ipAddressSchema) return <IpamSummarySkeleton />;

  const permission = getPermission(data[ipAddressKind]?.permissions?.edges);

  if (error) {
    return <ErrorScreen message="An error occurred while retrieving prefixes" />;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  const ipAddressData = data[ipAddressKind].edges[0].node;

  return (
    <div className="flex items-start gap-2">
      <IpDetailsCard
        schema={ipAddressSchema}
        data={ipAddressData}
        refetch={refetch}
        permission={permission}
      />
    </div>
  );
};
