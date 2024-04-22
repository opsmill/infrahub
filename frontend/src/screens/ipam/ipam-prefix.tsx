import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { Table } from "../../components/table/table";
import { Link } from "../../components/utils/link";
import { IPAM_PREFIX_OBJECT } from "../../config/constants";
import { GET_PREFIXES } from "../../graphql/queries/ipam/prefixes";
import useQuery from "../../hooks/useQuery";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { constructPathForIpam } from "./common/utils";

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

export default function IpamIPPrefix() {
  const { prefix } = useParams();

  const { loading, error, data } = useQuery(GET_PREFIXES, { variables: { prefix: prefix } });

  const parent = data && data[IPAM_PREFIX_OBJECT]?.edges[0]?.node?.parent?.node;

  const parentLink = parent?.prefix?.value
    ? constructPathForIpam(`/ipam/prefixes/${encodeURIComponent(parent?.prefix?.value)}`)
    : constructPathForIpam("/ipam/prefixes");

  const rows =
    data &&
    data[IPAM_PREFIX_OBJECT]?.edges.reduce(
      (acc, edge) => [
        ...acc,
        ...edge.node.children.edges.map((child) => ({
          values: {
            ...child?.node,
            children_count: child?.node?.children?.edges?.length,
          },
          link: constructLink(child?.node),
        })),
      ],
      []
    );

  const columns = [
    {
      name: "display_label",
      label: "Name",
    },
    {
      name: "children_count",
      label: "Children",
    },
  ];

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      <div className="flex items-center mb-2">
        <Link to={parentLink}>{parent?.display_label ?? "All prefixes"}</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix ?? "ok"}</span>
      </div>

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}
    </div>
  );
}
