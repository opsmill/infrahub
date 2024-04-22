import { useParams } from "react-router-dom";
import { Table } from "../../../components/table/table";
import { Link } from "../../../components/utils/link";
import { Pagination } from "../../../components/utils/pagination";
import { IPAM_IP_ADDRESS_OBJECT } from "../../../config/constants";
import { GET_IP_ADDRESSES } from "../../../graphql/queries/ipam/ip-address";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IPAM_QSP, IPAM_TABS } from "../constants";
import { constructPathForIpam } from "../common/utils";

export default function IpamIPAddressesList() {
  const { prefix } = useParams();

  const constructLink = (data) => {
    if (prefix) {
      return constructPathForIpam(
        `/ipam/prefixes/${encodeURIComponent(prefix)}/${encodeURIComponent(data?.address?.value)}`
      );
    }

    return constructPathForIpam(`/ipam/ip-addresses/${encodeURIComponent(data?.address?.value)}`);
  };

  const { loading, error, data } = useQuery(GET_IP_ADDRESSES, { variables: { prefix: prefix } });

  const columns = [
    { name: "address", label: "Address" },
    { name: "description", label: "Description" },
    { name: "interface", label: "Interface" },
    { name: "ip_namespace", label: "Ip Namespace" },
    { name: "ip_prefix", label: "Ip Prefix" },
  ];

  const rows =
    data &&
    data[IPAM_IP_ADDRESS_OBJECT]?.edges.map((edge) => ({
      values: {
        address: edge?.node?.address?.value,
        description: edge?.node?.description?.value,
        interface: edge?.node?.interface?.node?.display_label,
        ip_namespace: edge?.node?.ip_namespace?.node?.display_label,
        ip_prefix: edge?.node?.ip_prefix?.node?.display_label,
      },
      link: constructLink(edge?.node),
    }));

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      {prefix && (
        <div className="flex items-center mb-2">
          <span className="mr-2">Prefix:</span>
          <Link
            to={constructPathForIpam(
              `/ipam/prefixes/${encodeURIComponent(prefix)}?${IPAM_QSP}=${IPAM_TABS.PREFIX_DETAILS}`
            )}>
            {prefix}
          </Link>
        </div>
      )}

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}

      <Pagination count={data && data[IPAM_IP_ADDRESS_OBJECT]?.count} />
    </div>
  );
}
