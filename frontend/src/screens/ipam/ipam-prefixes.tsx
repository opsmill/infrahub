import { useParams } from "react-router-dom";
import { Table } from "../../components/table/table";
import { GET_PREFIXES } from "../../graphql/queries/ipam/prefixes";
import useQuery from "../../hooks/useQuery";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { constructPathForIpam } from "./common/utils";
import { IP_PREFIX_GENERIC } from "./constants";

const constructLink = (data) => {
  switch (data.__typename) {
    case IP_PREFIX_GENERIC: {
      return constructPathForIpam(`/ipam/prefixes/${encodeURIComponent(data?.prefix?.value)}`);
    }
    default: {
      return constructPathForIpam(`/ipam/ip_address/${encodeURIComponent(data?.prefix?.value)}`);
    }
  }
};

export default function IpamIPPrefixes() {
  const { prefix } = useParams();

  const { loading, error, data } = useQuery(GET_PREFIXES, { variables: { prefix: prefix } });

  const rows =
    data &&
    data[IP_PREFIX_GENERIC]?.edges.map((edge) => ({
      values: {
        ...edge?.node,
        children_count: edge?.node?.children?.edges?.length,
      },
      link: constructLink(edge?.node),
    }));

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
    return <ErrorScreen message="An error occurred while retrieving prefixes" />;
  }

  return (
    <div>
      <div>Prefixes</div>

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}
    </div>
  );
}
