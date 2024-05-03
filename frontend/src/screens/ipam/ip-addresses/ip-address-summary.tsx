import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useParams } from "react-router-dom";
import { Link } from "../../../components/utils/link";
import { GET_IP_ADDRESS_KIND } from "../../../graphql/queries/ipam/ip-address";
import useQuery from "../../../hooks/useQuery";
import { genericsState, schemaState } from "../../../state/atoms/schema.atom";
import { getSchemaObjectColumns } from "../../../utils/getSchemaObjectColumns";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IpDetailsCard } from "../common/ip-details-card";
import { constructPathForIpam } from "../common/utils";
import { IP_ADDRESS_GENERIC, IPAM_ROUTE } from "../constants";
import { IpamSummarySkeleton } from "../prefixes/ipam-summary-skeleton";
import { getObjectDetailsPaginated } from "../../../graphql/queries/objects/getObjectDetails";

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
    <div>
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
    })
  );

  const { loading, data, error, refetch } = useQuery(query, {
    skip: !ipAddressKind,
    notifyOnNetworkStatusChange: true,
  });

  if (loading || !data || !ipAddressSchema) return <IpamSummarySkeleton />;

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  const ipAddressData = data[ipAddressKind].edges[0].node;

  return (
    <div className="flex items-start gap-2">
      <IpDetailsCard schema={ipAddressSchema} data={ipAddressData} refetch={refetch} />
    </div>
  );
};
