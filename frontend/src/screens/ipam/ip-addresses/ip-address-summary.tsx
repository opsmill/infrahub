import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { Link } from "../../../components/utils/link";
import { GET_IP_ADDRESS_KIND } from "../../../graphql/queries/ipam/ip-address";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IP_ADDRESS_GENERIC, IPAM_ROUTE } from "../constants";
import { useAtomValue } from "jotai/index";
import { genericsState, schemaState } from "../../../state/atoms/schema.atom";
import { getObjectAttributes, getObjectRelationships } from "../../../utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { getObjectItemsPaginated } from "../../../graphql/queries/objects/getObjectItems";
import { IpDetailsCard } from "../common/ip-details-card";
import { constructPathForIpam } from "../common/utils";
import { IpamSummarySkeleton } from "../prefixes/ipam-summary-skeleton";

export default function IpAddressSummary() {
  const { prefix, ip_address } = useParams();

  const { loading, data } = useQuery(GET_IP_ADDRESS_KIND, {
    variables: {
      ip: ip_address,
    },
  });

  if (loading || !data) return <IpamSummarySkeleton />;

  const parentLink = prefix
    ? constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(prefix)}`)
    : constructPathForIpam(IPAM_ROUTE.ADDRESSES);

  const ipAddressKind = data[IP_ADDRESS_GENERIC].edges[0].node.__typename;

  return (
    <div>
      <div className="flex items-center mb-2">
        <Link to={parentLink}>All IP Addresses</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{ip_address}</span>
      </div>

      {loading && <LoadingScreen hideText />}

      <IpAddressSummaryContent ipAddressKind={ipAddressKind} />
    </div>
  );
}

const IpAddressSummaryContent = ({ ipAddressKind }: { ipAddressKind: string }) => {
  const { ip_address } = useParams();
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const ipAddressSchema = [...nodes, ...generics].find(({ kind }) => kind === ipAddressKind);

  const attributes = getObjectAttributes(ipAddressSchema);
  const relationships = getObjectRelationships(ipAddressSchema);

  const query = gql(
    getObjectItemsPaginated({
      kind: ipAddressKind,
      attributes,
      relationships,
      filters: `address__value: "${ip_address}"`,
    })
  );

  const { loading, data, error } = useQuery(query, {
    skip: !ipAddressKind,
    notifyOnNetworkStatusChange: true,
  });

  if (loading || !data || !ipAddressSchema) return <IpamSummarySkeleton />;

  if (error) {
    return <ErrorScreen message="An error occurred while retrieving prefixes" />;
  }

  const ipAddressData = data[ipAddressKind].edges[0].node;

  return (
    <div className="flex items-start gap-2">
      <IpDetailsCard schema={ipAddressSchema} data={ipAddressData} />
    </div>
  );
};
