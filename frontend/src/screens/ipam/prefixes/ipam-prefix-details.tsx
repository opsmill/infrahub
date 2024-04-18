import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import ProgressBar from "../../../components/stats/progress-bar";
import { Table } from "../../../components/table/table";
import { Link } from "../../../components/utils/link";
import { Pagination } from "../../../components/utils/pagination";
import { IPAM_PREFIX_OBJECT } from "../../../config/constants";
import { GET_PREFIX } from "../../../graphql/queries/ipam/prefixes";
import useQuery from "../../../hooks/useQuery";
import { constructPath } from "../../../utils/fetch";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IPAM_QSP } from "../constants";

export default function IpamIPPrefixDetails() {
  const { prefix } = useParams();
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);

  if (!prefix) {
    return <div>Select a prefix</div>;
  }

  const constructLink = (data) => {
    switch (data.__typename) {
      case IPAM_PREFIX_OBJECT: {
        return constructPath(`/ipam/prefixes/${encodeURIComponent(data?.prefix?.value)}`, [
          { name: IPAM_QSP, value: qspTab },
        ]);
      }
      default: {
        return constructPath(`/ipam/ip_address/${encodeURIComponent(data?.prefix?.value)}`, [
          { name: IPAM_QSP, value: qspTab },
        ]);
      }
    }
  };

  const { loading, error, data } = useQuery(GET_PREFIX, { variables: { prefix: prefix } });

  const parent = data && data[IPAM_PREFIX_OBJECT]?.edges[0]?.node?.parent?.node;

  const children = data && data[IPAM_PREFIX_OBJECT]?.edges[0]?.node?.children;

  const parentLink = parent?.prefix?.value
    ? constructPath(`/ipam/prefixes/${encodeURIComponent(parent?.prefix?.value)}`, [
        { name: IPAM_QSP, value: qspTab },
      ])
    : constructPath("/ipam/prefixes");

  const columns = [
    { name: "prefix", label: "Prefix" },
    { name: "description", label: "Description" },
    { name: "member_type", label: "Member Type" },
    { name: "is_pool", label: "Is Pool" },
    { name: "is_top_level", label: "Is Top Level" },
    { name: "utilization", label: "Utilization" },
    { name: "netmask", label: "Netmask" },
    { name: "hostmask", label: "Hostmask" },
    { name: "network_address", label: "Network Address" },
    { name: "broadcast_address", label: "Broadcast Address" },
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
        <Link to={parentLink}>{parent?.display_label ?? "All Prefixes"}</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix}</span>
      </div>

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}

      <Pagination count={children?.count} />
    </div>
  );
}
