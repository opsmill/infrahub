import { Link } from "@/components/ui/link";
import { GET_IP_ADDRESS_KIND } from "@/graphql/queries/ipam/ip-address";
import { getObjectDetailsPaginated } from "@/graphql/queries/objects/getObjectDetails";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "@/screens/errors/error-screen";
import UnauthorizedScreen from "@/screens/errors/unauthorized-screen";
import { IpDetailsCard } from "@/screens/ipam/common/ip-details-card";
import { constructPathForIpam } from "@/screens/ipam/common/utils";
import { IPAM_ROUTE, IP_ADDRESS_GENERIC } from "@/screens/ipam/constants";
import { IpamSummarySkeleton } from "@/screens/ipam/prefixes/ipam-summary-skeleton";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { getPermission } from "@/screens/permission/utils";
import { genericsState, schemaState } from "@/state/atoms/schema.atom";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useParams } from "react-router-dom";

export default function IpAddressSummary() {
  const { prefix, ip_address } = useParams();

  const { loading, data } = useQuery(GET_IP_ADDRESS_KIND, {
    variables: {
      ids: [ip_address],
    },
  });

  if (loading || !data) return <IpamSummarySkeleton />;

  const parentLink = prefix
    ? constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${prefix}`)
    : constructPathForIpam(IPAM_ROUTE.ADDRESSES);

  const ipAddressData = data[IP_ADDRESS_GENERIC].edges[0].node;

  return (
    <div className="flex flex-col flex-grow">
      <div className="flex items-center mb-2">
        <Link to={parentLink}>All IP Addresses</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{ipAddressData.display_label}</span>
      </div>

      {loading && <LoadingScreen hideText />}

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
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const ipAddressSchema = [...nodes, ...generics].find(({ kind }) => kind === ipAddressKind);

  const columns = getSchemaObjectColumns({ schema: ipAddressSchema });

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
