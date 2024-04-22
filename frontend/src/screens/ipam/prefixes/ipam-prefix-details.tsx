import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import ProgressBar from "../../../components/stats/progress-bar";
import { Table } from "../../../components/table/table";
import { Link } from "../../../components/utils/link";
import { Pagination } from "../../../components/utils/pagination";
import { IPAM_PREFIX_OBJECT } from "../../../config/constants";
import { GET_PREFIX } from "../../../graphql/queries/ipam/prefixes";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { constructPathForIpam } from "../common/utils";

export default function IpamIPPrefixDetails() {
  const { prefix } = useParams();

  if (!prefix) {
    return <div>Select a prefix</div>;
  }

  const constructLink = (data) => {
    switch (data.__typename) {
      case IPAM_PREFIX_OBJECT: {
        return constructPathForIpam(`/ipam/prefixes/${encodeURIComponent(data?.prefix?.value)}`);
      }
      default: {
        return constructPathForIpam(`/ipam/ip_address/${encodeURIComponent(data?.prefix?.value)}`);
      }
    }
  };

  const { loading, error, data } = useQuery(GET_PREFIX, { variables: { prefix: prefix } });

  const parent = data && data[IPAM_PREFIX_OBJECT]?.edges[0]?.node?.parent?.node;
  console.log("data: ", data);
  console.log("parent: ", parent);

  const children = data && data[IPAM_PREFIX_OBJECT]?.edges[0]?.node?.children;

  const parentLink = parent?.prefix?.value
    ? constructPathForIpam(`/ipam/prefixes/${encodeURIComponent(parent?.prefix?.value)}`)
    : "";

  const columns = [
    { name: "prefix", label: "Prefix" },
    { name: "description", label: "Description" },
    { name: "member_type", label: "Member Type" },
    { name: "is_pool", label: "Is Pool" },
    { name: "is_top_level", label: "Is Top Level" },
    { name: "utilization", label: "Utilization" },
    { name: "ip_namespace", label: "Ip Namespace" },
  ];

  const rows = children?.edges?.map((child) => ({
    values: {
      prefix: child?.node?.prefix?.value,
      description: child?.node?.description?.value,
      member_type: child?.node?.member_type?.value,
      is_pool: child?.node?.is_pool?.value ? <Icon icon="mdi:check" /> : <Icon icon="mdi:close" />,
      is_top_level: child?.node?.is_top_level?.value ? (
        <Icon icon="mdi:check" />
      ) : (
        <Icon icon="mdi:close" />
      ),
      utilization: <ProgressBar value={child?.node?.utilization?.value} />,
      netmask: child?.node?.netmask?.value,
      hostmask: child?.node?.hostmask?.value,
      network_address: child?.node?.network_address?.value,
      broadcast_address: child?.node?.broadcast_address?.value,
      ip_namespace: child?.node?.ip_namespace?.node?.display_label,
    },
    link: constructLink(child?.node),
  }));

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      <div className="flex items-center mb-2">
        {parentLink && (
          <>
            <Link to={parentLink}>{parent?.display_label}</Link>
            <Icon icon={"mdi:chevron-right"} />
          </>
        )}
        <span>{prefix}</span>
      </div>

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}

      <Pagination count={children?.count} />
    </div>
  );
}
