import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import ProgressBar from "../../../components/stats/progress-bar";
import { Table } from "../../../components/table/table";
import { Pagination } from "../../../components/utils/pagination";
import { IPAM_PREFIX_OBJECT } from "../../../config/constants";
import { GET_PREFIXES } from "../../../graphql/queries/ipam/prefixes";
import useQuery from "../../../hooks/useQuery";
import { constructPath } from "../../../utils/fetch";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IPAM_QSP } from "../constants";

export default function IpamIPPrefixesSummaryList() {
  const { prefix } = useParams();
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);

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

  const { loading, error, data } = useQuery(GET_PREFIXES, { variables: { prefix: prefix } });

  const columns = [
    { name: "prefix", label: "Prefix" },
    { name: "description", label: "Description" },
    { name: "member_type", label: "Member Type" },
    { name: "is_pool", label: "Is Pool" },
    { name: "is_top_level", label: "Is Top Level" },
    { name: "utilization", label: "Utilization" },
    { name: "ip_namespace", label: "Ip Namespace" },
    { name: "parent", label: "Parent" },
  ];

  const rows =
    data &&
    data[IPAM_PREFIX_OBJECT]?.edges.map((edge) => ({
      values: {
        prefix: edge?.node?.prefix?.value,
        description: edge?.node?.description?.value,
        member_type: edge?.node?.member_type?.value,
        is_pool: edge?.node?.is_pool?.value ? <Icon icon="mdi:check" /> : <Icon icon="mdi:close" />,
        is_top_level: edge?.node?.is_top_level?.value ? (
          <Icon icon="mdi:check" />
        ) : (
          <Icon icon="mdi:close" />
        ),
        utilization: <ProgressBar value={edge?.node?.utilization?.value} />,
        netmask: edge?.node?.netmask?.value,
        hostmask: edge?.node?.hostmask?.value,
        network_address: edge?.node?.network_address?.value,
        broadcast_address: edge?.node?.broadcast_address?.value,
        ip_namespace: edge?.node?.ip_namespace?.node?.display_label,
        parent: edge?.node?.parent?.node?.display_label,
      },
      link: constructLink(edge?.node),
    }));

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      {loading && <LoadingScreen hideText />}
      {data && <Table rows={rows} columns={columns} />}
      <Pagination count={data && data[IPAM_PREFIX_OBJECT]?.count} />
    </div>
  );
}
